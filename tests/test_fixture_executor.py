import time
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from test_fixture_registry import TARGET,BLUEPRINT

class Provider:
    """External system double with observable persisted objects, no registry mocks."""
    def __init__(self):self.objects={};self.creates=0;self.unknown=False
    def capabilities(self,target):return ['member']
    def find(self,bp,target):return [o for o in self.objects.values() if o['key']==bp['fixture_key']]
    def create(self,bp,target):
        self.creates+=1
        obj={'key':bp['fixture_key'],'id':'m'+str(self.creates)};self.objects[obj['id']]=obj
        if self.unknown:raise TimeoutError()
        return obj
    def detail(self,obj,bp,target):return {'local_id':obj['id'],'target':target,'attributes':{'active':True},'observed_at':time.time(),'evidence_ref':'detail.json'}

class ExecutorTests(unittest.TestCase):
    def setUp(self):
        from ai_test_framework.fixtures.registry import Registry,FixtureError
        from ai_test_framework.fixtures.executor import prepare,apply
        self.prepare=prepare;self.apply=apply;self.Error=FixtureError
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.r=Registry(Path(self.t.name)/'db');self.r.add_target(TARGET);self.r.add_blueprints([BLUEPRINT]);self.p=Provider()
        self.need={'requirement_id':'REQ-DEMO','case_id':'CASE-001','fixture_key':'member.smoke','version':'1','usage':'read'}
    def plan(self):return self.prepare(self.r,[self.need],'sit-shop',self.p.capabilities(TARGET))
    def test_plan_is_offline_and_apply_is_idempotent(self):
        plan=self.plan();self.assertEqual(self.p.creates,0)
        result=self.apply(self.r,plan,self.p,plan['sha256']);self.assertEqual(result['status'],'ready')
        self.apply(self.r,plan,self.p,plan['sha256']);self.assertEqual(self.p.creates,1)
        self.assertEqual(self.r.resolve('member.smoke','1','sit-shop')['local_id'],'m1')
    def test_after_verified_hook_runs_only_after_binding_health_and_step_journal(self):
        calls=[]
        def after(bp,target,observation):
            binding=self.r.resolve(bp['fixture_key'],bp['version'],target['target_ref'])
            self.assertEqual(binding['local_id'],observation['local_id'])
            with self.r.tx()as db:
                self.assertEqual(db.execute("select state from intents where step='member.smoke'").fetchone()[0],'verified')
            calls.append(bp['fixture_key'])
        self.p.after_verified=after;plan=self.plan()
        self.assertEqual(self.apply(self.r,plan,self.p,plan['sha256'])['status'],'ready')
        self.assertEqual(calls,['member.smoke'])
        self.p.unknown=True;self.p.objects={}
        # Unknown writes never call a post-verification release hook.
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'another'}]);need={**self.need,'fixture_key':'another'}
        plan=self.prepare(self.r,[need],'sit-shop',['member']);self.apply(self.r,plan,self.p,plan['sha256'])
        self.assertEqual(calls,['member.smoke'])
    def test_unknown_create_is_never_resent_even_with_new_plan(self):
        plan=self.plan();self.p.unknown=True
        self.assertEqual(self.apply(self.r,plan,self.p,plan['sha256'])['status'],'blocked')
        self.p.unknown=False
        self.assertEqual(self.apply(self.r,self.plan(),self.p,self.plan()['sha256'])['status'],'blocked')
        self.assertEqual(self.p.creates,1)
    def test_tampered_plan_or_unapproved_hash_has_no_side_effect(self):
        p=self.plan();p['target']['salon']='other'
        with self.assertRaises(self.Error):self.apply(self.r,p,self.p,p['sha256'])
        p=self.plan()
        with self.assertRaises(self.Error):self.apply(self.r,p,self.p,'wrong')
        self.assertEqual(self.p.creates,0)
    def test_multiple_matches_block_without_creating_or_binding(self):
        self.p.objects={'a':{'id':'a','key':'member.smoke'},'b':{'id':'b','key':'member.smoke'}}
        p=self.plan();self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'blocked');self.assertEqual(self.p.creates,0)
    def test_dependency_order_and_missing_capability(self):
        self.r.add_blueprints([{**BLUEPRINT,'fixture_key':'appointment','entity':'appointment','requires':[{'fixture_key':'member.smoke','version':'1'}]}])
        need={**self.need,'fixture_key':'appointment'}
        plan=self.prepare(self.r,[need],'sit-shop',['member'])
        self.assertEqual([s['blueprint']['fixture_key'] for s in plan['steps']],['member.smoke','appointment'])
        self.assertEqual(plan['status'],'blocked');self.assertEqual(plan['steps'][-1]['reason'],'provider_capability_missing')
    def test_provider_recipe_change_invalidates_authorization(self):
        self.p.contract=lambda:{'recipe':'one'}
        p=self.prepare(self.r,[self.need],'sit-shop',['member'],self.p.contract())
        self.p.contract=lambda:{'recipe':'changed'}
        with self.assertRaises(self.Error):self.apply(self.r,p,self.p,p['sha256'])
        self.assertEqual(self.p.creates,0)
    def test_unknown_write_reconciles_by_readback_without_second_create(self):
        from ai_test_framework.fixtures.executor import reconcile
        p=self.plan();self.p.unknown=True
        self.apply(self.r,p,self.p,p['sha256']);self.p.unknown=False
        result=reconcile(self.r,p,self.p)
        self.assertEqual(result['status'],'reconciled',result)
        self.assertEqual(self.p.creates,1)
        self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'ready')
        self.assertEqual(self.p.creates,1)

    def test_input_reconciliation_preserves_separate_unknown_execution_owner(self):
        from ai_test_framework.fixtures.executor import reconcile
        from ai_test_framework.fixtures import coordination
        p=self.plan();self.p.unknown=True;self.apply(self.r,p,self.p,p['sha256']);self.p.unknown=False
        claim=coordination.acquire(self.r,'RUN-OWNER',['employee-training:example'],p['sha256'])
        coordination.release(self.r,claim,'unknown','original-run')
        result=reconcile(self.r,p,self.p)
        self.assertEqual(result['status'],'reconciled');self.assertEqual(self.p.creates,1)
        with self.r.tx() as db:
            row=db.execute('select state,body from intents where id=?',(claim['resource_ids'][0],)).fetchone()
            self.assertEqual(row['state'],'unknown')
            import json
            self.assertEqual(json.loads(row['body']),claim)

    def test_unrecognized_unknown_business_intent_still_blocks_reconciliation(self):
        from ai_test_framework.fixtures.executor import reconcile
        p=self.plan();self.p.unknown=True;self.apply(self.r,p,self.p,p['sha256']);self.p.unknown=False
        with self.r.tx() as db:db.execute('insert into intents values(?,?,?,?,?)',('other-effect',p['sha256'],'other-business','unknown','{}'))
        with self.assertRaisesRegex(self.Error,'UNKNOWN_INTENTS_REMAIN'):reconcile(self.r,p,self.p)

    def test_distinct_store_instances_have_distinct_intents(self):
        class StoreProvider(Provider):
            def find(self,bp,target):return [o for o in self.objects.values() if o['salon']==target['salon']]
            def create(self,bp,target):
                obj=super().create(bp,target);obj['salon']=target['salon'];return obj
        self.p=StoreProvider();p=self.plan()
        self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'ready')
        t={**TARGET,'target_ref':'other','salon':'other'};self.r.add_target(t)
        p=self.prepare(self.r,[self.need],'other',['member'])
        self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'ready')
        self.assertEqual(self.p.creates,2)

    def test_missing_existing_binding_blocks_before_create(self):
        self.r.bind('member.smoke','1','sit-shop','historical-id')
        p=self.plan();result=self.apply(self.r,p,self.p,p['sha256'])
        self.assertEqual(result['status'],'blocked');self.assertEqual(self.p.creates,0)


class AbsentRetryTests(unittest.TestCase):
    setUp=ExecutorTests.setUp
    plan=ExecutorTests.plan
    def rejected(self):
        p=self.plan()
        self.p.create=lambda *args: (_ for _ in ()).throw(TimeoutError())
        self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'blocked')
        return p
    def proof(self,p):
        from ai_test_framework.fixtures.registry import digest
        with self.r.tx() as db:scope=dict(db.execute("select * from intents where step='scope'").fetchone())
        return dict(plan_sha256=p['sha256'],previous_scope_sha256=digest(scope),observed_at=time.time(),evidence_ref='fresh-absence.json',settled=True,absent_keys=['member.smoke'])
    def test_fresh_settled_absence_and_explicit_new_authorization_allows_one_new_attempt(self):
        from ai_test_framework.fixtures.executor import authorize_absent_retry
        p=self.rejected();proof=self.proof(p)
        result=authorize_absent_retry(self.r,p,self.p,proof,p['sha256'])
        self.assertEqual(result['status'],'reconciled_absent')
        self.p=Provider();self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'ready')
        self.assertEqual(self.p.creates,1)
    def test_absence_recovery_rejects_unsettled_stale_wrong_scope_and_existing_object(self):
        from ai_test_framework.fixtures.executor import authorize_absent_retry
        p=self.rejected()
        for change in [dict(settled=False),dict(observed_at=time.time()-100),dict(plan_sha256='b'*64),dict(absent_keys=[])]:
            with self.assertRaises(self.Error):authorize_absent_retry(self.r,p,self.p,{**self.proof(p),**change},p['sha256'])
        self.p.objects={'m1':dict(key='member.smoke',id='m1')}
        with self.assertRaises(self.Error):authorize_absent_retry(self.r,p,self.p,self.proof(p),p['sha256'])

    def test_prior_attempt_settlement_proof_cannot_authorize_a_later_unknown_attempt(self):
        from ai_test_framework.fixtures.executor import authorize_absent_retry
        p=self.rejected();proof=self.proof(p)
        authorize_absent_retry(self.r,p,self.p,proof,p['sha256'])
        self.assertEqual(self.apply(self.r,p,self.p,p['sha256'])['status'],'blocked')
        with self.assertRaises(self.Error):authorize_absent_retry(self.r,p,self.p,proof,p['sha256'])
