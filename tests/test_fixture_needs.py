import json
import tempfile
import unittest
from pathlib import Path
from test_fixture_registry import TARGET, BLUEPRINT
from ai_test_framework.fixtures.registry import Registry, FixtureError
from ai_test_framework.fixtures.needs import record, freeze, readiness, align


class NeedsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.r=Registry(Path(self.tmp.name)/'registry.db')
        self.r.add_target(TARGET); self.r.add_blueprints([BLUEPRINT])
        self.need={'requirement_id':'REQ-1','case_id':'CASE-1','fixture_key':'member.smoke','version':'1','usage':'read'}

    def test_incremental_dedup_freeze_and_conflicting_case_binding(self):
        record(self.r,'RUN-1',self.need); record(self.r,'RUN-1',self.need)
        result=freeze(self.r,'RUN-1')
        self.assertEqual(result['needs'],[self.need]); self.assertEqual(result,freeze(self.r,'RUN-1'))
        with self.assertRaises(FixtureError):record(self.r,'RUN-1',{**self.need,'case_id':'CASE-2'})
        record(self.r,'RUN-2',self.need)
        with self.assertRaises(FixtureError):record(self.r,'RUN-2',{**self.need,'version':'2'})

    def test_missing_fixture_blocks_only_dependent_case(self):
        self.r.bind('member.smoke','1','sit-shop','m1')
        self.r.observe('member.smoke','1','sit-shop',dict(local_id='m1',target=TARGET,attributes={'active':True},evidence_ref='run/read'))
        result=readiness(self.r,[self.need,{**self.need,'case_id':'CASE-2','fixture_key':'missing'}],'sit-shop')
        self.assertEqual([x['fixture_status'] for x in result['cases']],['ready','blocked'])
        self.assertEqual(result['authority'],'fixture_preconditions_only')

    def test_same_key_different_price_fails_alignment(self):
        other={**TARGET,'target_ref':'99-shop','stage':'prd','zone':'z99','salon':'shop-b'}
        self.r.add_target(other)
        for t,price in [(TARGET,100),(other,200)]:
            self.r.bind('member.smoke','1',t['target_ref'],'m1')
            self.r.observe('member.smoke','1',t['target_ref'],dict(local_id='m1',target=t,attributes={'active':True,'price':price},evidence_ref='r'))
        self.assertEqual(align(self.r,'member.smoke','1',['sit-shop','99-shop'],['active'])['status'],'aligned')
        self.assertEqual(align(self.r,'member.smoke','1',['sit-shop','99-shop'],['price'])['status'],'drift')

if __name__=='__main__':unittest.main()
