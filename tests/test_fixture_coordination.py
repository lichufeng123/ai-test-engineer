import copy
import multiprocessing
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ai_test_framework.fixtures.registry import Registry, FixtureError, digest
from ai_test_framework.fixtures.coordination import acquire, release, recover


def compete(path, start, queue, owner):
    start.wait(5)
    try:
        acquire(Registry(path), owner, ['shared-ui'], 'a' * 64)
        queue.put('acquired')
    except FixtureError as exc:
        queue.put(str(exc))


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'pool.sqlite3'
        self.registry = Registry(self.path)
        self.resources = ['ui-context:a', 'employee-training:z99:1:2:1104']

    def claim(self):
        return acquire(self.registry, 'RUN-A', self.resources, 'a' * 64)

    def proof(self, claim):
        return dict(owner_run=claim['owner_run'], holder_id=claim['holder_id'],
                    context_sha256=claim['context_sha256'],
                    resources_sha256=digest(claim['resources']),
                    observed_at=time.time(), evidence_ref='run/readonly-session-proof.json')

    def test_overlapping_set_is_atomic_and_same_owner_is_not_reentrant(self):
        claim = self.claim()
        for owner in ['RUN-B', 'RUN-A']:
            with self.assertRaisesRegex(FixtureError, 'EXECUTION_RESOURCE_BUSY'):
                acquire(self.registry, owner, ['new-slot', self.resources[0]], 'b' * 64)
        with self.registry.tx() as db:
            self.assertEqual(db.execute("select count(*) from intents where step='execution-owner-claim'").fetchone()[0], 2)
        release(self.registry, claim, 'released', 'run/complete.json')
        self.assertNotEqual(acquire(self.registry, 'RUN-B', self.resources, 'b' * 64)['holder_id'], claim['holder_id'])

    def test_unrelated_execution_resources_can_progress_together(self):
        self.claim()
        other = acquire(self.registry, 'RUN-B', ['another-ui', 'another-employee'], 'b' * 64)
        self.assertEqual(other['owner_run'], 'RUN-B')

    def test_wrong_owner_or_partial_release_never_frees_any_resource(self):
        claim = self.claim()
        for change in [dict(owner_run='RUN-B'), dict(holder_id='other'), dict(resources=claim['resources'][:1])]:
            with self.assertRaises(FixtureError):
                release(self.registry, {**claim, **change}, 'released', 'run/proof.json')
        with self.assertRaises(FixtureError):
            acquire(self.registry, 'RUN-B', self.resources, 'b' * 64)

    def test_unknown_or_crashed_owner_is_not_freed_by_age_or_claimant(self):
        claim = self.claim()
        release(self.registry, claim, 'unknown', 'run/interrupted.json')
        with self.assertRaises(FixtureError):
            acquire(self.registry, 'RUN-B', self.resources, 'b' * 64)
        with self.assertRaisesRegex(FixtureError, 'EXECUTION_WRITER_ALIVE'):
            recover(self.registry, claim, self.proof(claim))
        with patch('ai_test_framework.fixtures.coordination._writer_alive', return_value=False):
            recover(self.registry, claim, self.proof(claim))
        next_claim = acquire(self.registry, 'RUN-B', self.resources, 'b' * 64)
        with patch('ai_test_framework.fixtures.coordination._writer_alive', return_value=False), self.assertRaises(FixtureError):
            recover(self.registry, claim, self.proof(claim))
        release(self.registry, next_claim, 'released', 'run/complete.json')

    def test_recovery_requires_exact_scope_fresh_proof_and_dead_writer(self):
        claim = self.claim()
        release(self.registry, claim, 'unknown', 'run/interrupted.json')
        for change in [dict(context_sha256='b' * 64), dict(holder_id='other'),
                       dict(resources_sha256='b' * 64), dict(observed_at=time.time() - 100),
                       dict(observed_at=True), dict(owner_run='RUN-B')]:
            with patch('ai_test_framework.fixtures.coordination._writer_alive', return_value=False), self.assertRaises(FixtureError):
                recover(self.registry, claim, {**self.proof(claim), **change})

    def test_invalid_claim_scope_fails_before_any_reservation(self):
        for resources, context in [([], 'a' * 64), (['same', 'same'], 'a' * 64),
                                   (['x'], 'latest'), (['Bearer private'], 'a' * 64)]:
            with self.assertRaises(FixtureError):
                acquire(self.registry, 'RUN-A', resources, context)
        with self.registry.tx() as db:
            self.assertEqual(db.execute('select count(*) from intents').fetchone()[0], 0)

    def test_two_processes_never_both_claim_the_same_execution_context(self):
        ctx = multiprocessing.get_context('spawn')
        start, queue = ctx.Event(), ctx.Queue()
        workers = [ctx.Process(target=compete, args=(self.path, start, queue, f'RUN-{i}')) for i in range(2)]
        for worker in workers:
            worker.start()
        start.set()
        results = [queue.get(timeout=10) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(sorted(results), ['EXECUTION_RESOURCE_BUSY', 'acquired'])


class NoEffectRecoveryTests(unittest.TestCase):
    setUp=CoordinationTests.setUp
    claim=CoordinationTests.claim
    proof=CoordinationTests.proof
    def setup_lease(self):
        from test_fixture_registry import TARGET,BLUEPRINT
        self.registry.add_target(TARGET)
        bp={**BLUEPRINT,'pool':'run'};self.registry.add_blueprints([bp]);self.registry.bind(bp['fixture_key'],'1',TARGET['target_ref'],'object-a')
        obs=dict(local_id='object-a',target=TARGET,attributes=bp['attributes'],observed_at=time.time(),evidence_ref='before')
        self.registry.observe(bp['fixture_key'],'1',TARGET['target_ref'],obs)
        lease=self.registry.acquire([dict(fixture_key=bp['fixture_key'],version='1',target_ref=TARGET['target_ref'],mode='write')],'RUN-A')
        with self.registry.tx() as db:lock=db.execute('select physical from locks where lease=?',(lease['lease_id'],)).fetchone()[0]
        return lease,{lock:{**obs,'observed_at':time.time(),'evidence_ref':'fresh-unchanged'}}
    def test_no_effect_recovery_requires_dead_owner_full_set_and_unchanged_native_evidence(self):
        from ai_test_framework.fixtures.coordination import recover_no_effect
        claim=self.claim();lease,obs=self.setup_lease()
        with self.assertRaisesRegex(FixtureError,'EXECUTION_WRITER_ALIVE'):recover_no_effect(self.registry,claim,self.proof(claim),lease['lease_id'],obs)
        with patch('ai_test_framework.fixtures.coordination._writer_alive',return_value=False):
            with self.assertRaises(FixtureError):recover_no_effect(self.registry,claim,self.proof(claim),lease['lease_id'],{})
            changed=copy.deepcopy(obs);next(iter(changed.values()))['attributes']={'active':False}
            with self.assertRaises(FixtureError):recover_no_effect(self.registry,claim,self.proof(claim),lease['lease_id'],changed)
            recover_no_effect(self.registry,claim,self.proof(claim),lease['lease_id'],obs)
        with self.registry.tx() as db:
            self.assertEqual(db.execute('select state from leases where id=?',(lease['lease_id'],)).fetchone()[0],'released')
            self.assertEqual(db.execute('select state from bindings').fetchone()[0],'healthy')

    def test_older_unchanged_receipt_cannot_overwrite_a_newer_registry_observation(self):
        from ai_test_framework.fixtures.coordination import recover_no_effect
        claim=self.claim();lease,observations=self.setup_lease();obs=next(iter(observations.values()))
        with self.registry.tx() as db:binding=dict(db.execute('select * from bindings').fetchone())
        newer={**obs,'observed_at':time.time(),'attributes':{**obs['attributes'],'after_effect':True}}
        self.registry.observe(binding['key'],binding['version'],binding['target'],newer)
        with patch('ai_test_framework.fixtures.coordination._writer_alive',return_value=False),self.assertRaises(FixtureError):
            recover_no_effect(self.registry,claim,self.proof(claim),lease['lease_id'],observations)
