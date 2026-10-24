import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ai_test_framework.cli import main
from test_fixture_registry import TARGET,BLUEPRINT
class FixtureCliTests(unittest.TestCase):
    def call(self,args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):rc=main(args)
        return rc,json.loads(out.getvalue())
    def test_register_catalog_resolve_and_prepare_without_business_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'input.json';p.write_text(json.dumps({'targets':[TARGET],'blueprints':[BLUEPRINT]}))
            rc,r=self.call(['fixture','register','--root',tmp,'--input',str(p)]);self.assertEqual(rc,0)
            rc,r=self.call(['fixture','catalog','--root',tmp]);self.assertEqual(len(r['blueprints']),1)
            rc,r=self.call(['fixture','resolve','--root',tmp,'--key','member.smoke','--version','1','--target','sit-shop']);self.assertEqual(rc,1);self.assertEqual(r['code'],'BINDING_MISSING')
            p.write_text(json.dumps({'needs':[{'requirement_id':'REQ-1','case_id':'CASE-1','fixture_key':'member.smoke','version':'1','usage':'read'}],'target_ref':'sit-shop','capabilities':['member']}))
            rc,r=self.call(['fixture','prepare','--root',tmp,'--input',str(p)]);self.assertEqual(rc,0);self.assertEqual(r['steps'][0]['operation'],'ensure')
    def test_unavailable_target_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc,r=self.call(['fixture','resolve','--root',tmp,'--key','member','--version','1','--target','missing'])
            self.assertEqual(rc,1);self.assertEqual(r['status'],'blocked')
