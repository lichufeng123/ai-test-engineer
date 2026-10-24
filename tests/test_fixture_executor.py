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
