import copy
import json
import multiprocessing
import sys
import tempfile
import unittest
import time
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))

TARGET = dict(target_ref='sit-shop', stage='sit', zone='z1', organization='brand-a', salon='shop-a', role='advisor', platform='api', build='v1')
BLUEPRINT = dict(fixture_key='member.smoke', version='1', entity='member', pool='base', attributes={'active': True}, requires=[])

def acquire_worker(path, queue):
    from ai_test_framework.fixtures.registry import Registry, FixtureError
    try:
        r=Registry(path); lease=r.acquire([{'fixture_key':'writable','version':'1','target_ref':'sit-shop','mode':'write'}], 'worker', 60)
        queue.put('acquired')
    except FixtureError as e: queue.put(str(e))

def initialize_worker(path, queue):
    from ai_test_framework.fixtures.registry import Registry
    try:Registry(path);queue.put('ok')
    except Exception:queue.put('failed')

class FixtureRegistryTests(unittest.TestCase):
    def setUp(self):
        from ai_test_framework.fixtures.registry import Registry, FixtureError
        self.Error=FixtureError;self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'pool.sqlite3';self.r=Registry(self.path)
        self.r.add_target(TARGET);self.r.add_blueprints([BLUEPRINT])
    def bind(self, key='member.smoke', version='1', target='sit-shop', local_id='m1'):
        self.r.bind(key,version,target,local_id)
        return self.r.observe(key,version,target,{'local_id':local_id,'target':self.r.target(target),'attributes':{'active':True},'observed_at':time.time(),'evidence_ref':'run/detail.json'},ttl=60)
    def ref(self, mode='read', key='member.smoke'):
        return dict(fixture_key=key,version='1',target_ref='sit-shop',mode=mode)
    def test_lease_claim_binding_is_atomic_and_requires_current_exact_owner(self):
        from ai_test_framework.fixtures import coordination
        self.bind();claim=coordination.acquire(self.r,'RUN-A',['workflow:one'],'a'*64)
        with self.assertRaises(self.Error):self.r.acquire([self.ref()],'RUN-B',owner_claim=claim)
        lease=self.r.acquire([self.ref()],'RUN-A',owner_claim=claim)
        with self.r.tx() as db:
            body=json.loads(db.execute("select body from audit where action='execution_dependency_lease'").fetchone()[0])
            self.assertEqual(body,dict(lease_id=lease['lease_id'],claim=claim,requests=[self.ref()]))
            self.assertEqual(db.execute('select count(*) from leases').fetchone()[0],1)
        coordination.release(self.r,claim,'released','done')
        with self.assertRaises(self.Error):self.r.acquire([self.ref()],'RUN-A',owner_claim=claim)
    def test_explicit_versions_coexist_and_are_immutable(self):
        self.bind();bp={**BLUEPRINT,'version':'2'};self.r.add_blueprints([bp]);self.bind(version='2',local_id='m2')
        self.assertEqual(self.r.resolve('member.smoke','1','sit-shop')['local_id'],'m1')
        self.assertEqual(self.r.resolve('member.smoke','2','sit-shop')['local_id'],'m2')
        with self.assertRaises(self.Error):self.r.add_blueprints([{**BLUEPRINT,'attributes':{'active':False}}])
        with self.assertRaises(self.Error):self.r.bind('member.smoke','1','sit-shop','different')
        with self.assertRaises(self.Error):self.r.resolve('member.smoke','latest','sit-shop')
    def test_missing_target_never_falls_back(self):
        self.bind()
        with self.assertRaises(self.Error):self.r.resolve('member.smoke','1','z99')
    def test_binding_must_have_fresh_identity_and_expected_attributes(self):
        self.r.bind('member.smoke','1','sit-shop','m1')
        with self.assertRaises(self.Error):self.r.resolve('member.smoke','1','sit-shop')
        wrong=dict(local_id='m1',target={**TARGET,'salon':'other'},attributes={'active':True},observed_at=time.time(),evidence_ref='x')
        with self.assertRaises(self.Error):self.r.observe('member.smoke','1','sit-shop',wrong)
        self.r.add_blueprints([{**BLUEPRINT,'version':'2'}]);self.bind(version='2',local_id='m2');bad=dict(local_id='m2',target=TARGET,attributes={'active':False},observed_at=time.time(),evidence_ref='x')
        with self.assertRaises(self.Error):self.r.observe('member.smoke','2','sit-shop',bad)
        with self.assertRaises(self.Error):self.r.resolve('member.smoke','1','sit-shop')
    def test_dependency_cycle_and_credentials_rejected_atomically(self):
        with self.assertRaises(self.Error):self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'a','requires':[{'fixture_key':'a','version':'1'}]}])
        with self.assertRaises(self.Error):self.r.add_blueprints([{**BLUEPRINT,'attributes':{'password':'do-not-store'}}])
        self.assertEqual(len(self.r.catalog()['blueprints']),1)
    def test_readers_share_and_write_cannot_take_shared_base(self):
        self.bind();self.r.acquire([self.ref()], 'one',60);self.r.acquire([self.ref()], 'two',60)
        with self.assertRaises(self.Error):self.r.acquire([self.ref('write')],'three',60)
    def test_physical_aliases_and_atomic_effect_set_lock(self):
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'alias','pool':'run'}]);self.bind();self.bind(key='alias')
        lease=self.r.acquire([self.ref()], 'reader',60)
        with self.assertRaises(self.Error):self.r.acquire([self.ref('write','alias')], 'writer',60)
        self.r.release(lease['lease_id'], 'reader', {'m1':{'local_id':'m1','target':TARGET,'attributes':{'active':True},'observed_at':time.time(),'evidence_ref':'fresh'}})
        self.r.acquire([self.ref('write','alias')],'writer',60)
        with self.assertRaises(self.Error):self.r.acquire([self.ref()], 'newreader',60)
    def test_expired_lease_blocks_until_reconciled_not_automatically_reused(self):
        self.bind();l=self.r.acquire([self.ref()], 'reader',1)
        import sqlite3
        with sqlite3.connect(self.path) as db:db.execute('update leases set expires=0')
        with self.assertRaises(self.Error):self.r.acquire([self.ref()], 'another',60)
        with self.assertRaises(self.Error):self.r.heartbeat(l['lease_id'],'reader',60)
    def test_writer_processes_cannot_both_acquire(self):
        self.r.add_blueprints([{**BLUEPRINT,'version':'2','pool':'run'}])
        # Two processes acquire the same physical entity through a writable alias.
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'writable','pool':'run'}]);self.bind(key='writable')
        self.bind()
        # Parent holds a reader. Child must fail even though it has a different SQLite connection.
        self.r.acquire([self.ref()], 'parent',60)
        ctx=multiprocessing.get_context('spawn');q=ctx.Queue();p=ctx.Process(target=acquire_worker,args=(str(self.path),q));p.start();p.join(10)
        self.assertFalse(p.is_alive());self.assertNotEqual(q.get(timeout=2),'acquired')
    def test_two_independent_writer_processes_have_one_winner(self):
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'writable','pool':'run'}]);self.bind(key='writable')
        ctx=multiprocessing.get_context('spawn');q=ctx.Queue()
        ps=[ctx.Process(target=acquire_worker,args=(str(self.path),q)) for _ in range(2)]
        for p in ps:p.start()
        for p in ps:p.join(10);self.assertFalse(p.is_alive())
        self.assertCountEqual([q.get(timeout=2) for _ in ps],['acquired','LEASE_CONFLICT'])
    def test_release_writer_accepts_changed_state_but_consumes_object(self):
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'writable','pool':'run'}]);self.bind(key='writable')
        l=self.r.acquire([self.ref('write','writable')],'writer')
        self.r.release(l['lease_id'],'writer',{'m1':dict(local_id='m1',target=TARGET,attributes={'active':False},observed_at=time.time(),evidence_ref='after')})
        with self.assertRaises(self.Error):self.r.resolve('writable','1','sit-shop')
    def test_initialization_is_transactional_across_processes(self):
        path=Path(self.tmp.name)/'new.db';ctx=multiprocessing.get_context('spawn');q=ctx.Queue()
        ps=[ctx.Process(target=initialize_worker,args=(str(path),q)) for _ in range(4)]
        for p in ps:p.start()
        for p in ps:p.join(10);self.assertFalse(p.is_alive())
        self.assertEqual([q.get(timeout=2) for _ in ps],['ok']*4)
        import sqlite3
        with sqlite3.connect(path) as db:self.assertEqual(db.execute('select count(*) from meta').fetchone()[0],1)
    def test_release_needs_readback_and_wrong_owner_cannot_release(self):
        self.bind();l=self.r.acquire([self.ref()], 'one',60)
        with self.assertRaises(self.Error):self.r.release(l['lease_id'],'other',{})
        with self.assertRaises(self.Error):self.r.release(l['lease_id'],'one',{})
        with self.assertRaises(self.Error):self.r.acquire([self.ref('write')],'two',60)

    def test_old_observation_cannot_refresh_health(self):
        b=self.bind();obs=b['observation']
        with patch('ai_test_framework.fixtures.registry.time.time',return_value=time.time()+1000):
            with self.assertRaises(self.Error):self.r.observe('member.smoke','1','sit-shop',obs)
        with self.assertRaises(self.Error):self.r.observe('member.smoke','1','sit-shop',obs)

    def test_lease_checks_health_expiry_and_fingerprint(self):
        self.bind();l=self.r.acquire([self.ref()],'reader')
        for state,expires in [('quarantined',time.time()+300),('healthy',0)]:
            with self.r.tx() as db:db.execute('update bindings set state=?,expires=?',(state,expires))
            with self.assertRaises(self.Error):self.r.assert_lease(l['lease_id'],'reader')
            with self.assertRaises(self.Error):self.r.heartbeat(l['lease_id'],'reader')
        with self.r.tx() as db:
            b=db.execute('select observed from bindings').fetchone();obs=json.loads(b[0]);obs['attributes']['extra']='changed'
            db.execute('update bindings set state=?,expires=?,observed=?',('healthy',time.time()+300,json.dumps(obs)))
        with self.assertRaises(self.Error):self.r.assert_lease(l['lease_id'],'reader')

    def test_cross_store_alias_cannot_bypass_lock_or_quarantine(self):
        other={**TARGET,'target_ref':'other-store','salon':'shop-b'};self.r.add_target(other)
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'writable','entity':'service','pool':'run'}])
        self.bind(key='writable');self.bind(key='writable',target='other-store')
        self.r.acquire([self.ref('write','writable')],'one')
        with self.assertRaises(self.Error):self.r.acquire([{**self.ref('write','writable'),'target_ref':'other-store'}],'two')
        with self.r.tx() as db:db.execute("update bindings set state='quarantined' where target='other-store'")
        with self.assertRaises(self.Error):self.r.resolve('writable','1','sit-shop')

    def test_schema_upgrade_requires_idle_leases_and_expires_old_health(self):
        from ai_test_framework.fixtures.registry import Registry,canonical
        self.bind();lease=self.r.acquire([self.ref()],'one')
        with self.r.tx() as db:
            db.execute('update meta set version=1')
            db.execute('update bindings set physical=?',(canonical(['sit','z1','brand-a','shop-a','member','m1']),))
        with self.assertRaisesRegex(self.Error,'SCHEMA_MIGRATION_ACTIVE_LEASES'):Registry(self.path)
        with self.r.tx() as db:db.execute("update leases set state='released'")
        upgraded=Registry(self.path)
        with self.assertRaises(self.Error):upgraded.resolve('member.smoke','1','sit-shop')
        with upgraded.tx() as db:
            self.assertEqual(db.execute('select version from meta').fetchone()[0],2)
            self.assertEqual(json.loads(db.execute('select physical from bindings').fetchone()[0]),['sit','z1','brand-a','member','m1'])

    def test_release_does_not_claim_healthy_after_external_quarantine(self):
        self.bind();l=self.r.acquire([self.ref()],'reader')
        with self.r.tx() as db:db.execute("update bindings set state='quarantined',expires=0")
        result=self.r.release(l['lease_id'],'reader',{'m1':dict(local_id='m1',target=TARGET,attributes={'active':True},observed_at=time.time(),evidence_ref='after')})
        self.assertEqual(result['outcomes'][0][1],'quarantined')
