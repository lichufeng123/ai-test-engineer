"""Engineering controls for the optional tracker adapter, no real endpoints."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
try:
    from ai_test_framework import defects
except ImportError:
    defects=None


class DefectAdapterTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(defects,'framework defect adapter is missing')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.script=self.root/'provider.py'
        self.script.write_text('''import sys,json,pathlib
args=sys.argv[1:];action=args[0]
log=pathlib.Path(__file__).with_suffix('.calls')
with log.open('a') as f:f.write(json.dumps(args)+'\\n')
if action=='versions':print(json.dumps({'status':'needs_selection','versions':[{'id':7,'name':'Synthetic build'}]}))
elif action=='select':
 out={'schema_version':1,'run_id':args[args.index('--run-id')+1],'scope':args[args.index('--scope')+1],'confirmed_by':args[args.index('--confirmed-by')+1],'builds':[{'id':7,'name':'Synthetic build'}]}
 pathlib.Path(args[args.index('--run')+1]).write_text(json.dumps(out));print(json.dumps(out))
elif action=='draft':print(json.dumps({'status':'draft','payload':{'title':'Synthetic defect'}}))
elif action in ('submit','verify'):print(json.dumps({'status':'verified','bug_id':42,'bug_url':'https://tracker.example.invalid/42','needs_owner_confirmation':False,'evidence':{'verified':True}}))
''')
        self.config=self.root/'adapter.json'
        defects.configure_adapter([sys.executable,str(self.script)],[],self.config)
        self.run=self.root/'run.json';self.run.write_text(json.dumps({'run_id':'RUN1','scope':'Synthetic scope','confirmed_by':'Reviewer','builds':[{'id':7,'name':'Synthetic build'}]}))
        self.issue=self.root/'issue.json';self.issue.write_text(json.dumps({'id':'ISSUE1','source':'automation','triage_file':'triage.json','candidate_id':'C1'}))
        self.triage=self.root/'triage.json';self.triage.write_text(json.dumps({'run_id':'RUN1','candidates':[{'candidate_id':'C1','status':'confirmed_defect','actual':'incorrect','expected':'correct'}]}))
    def call(self,action,**kw):
        return defects.run_adapter(self.config,action,run=self.run,issue=self.issue,**kw)
    def test_submit_requires_explicit_write_permission(self):
        result=self.call('submit')
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(self.script.with_suffix('.calls').exists())
    def test_source_hash_drift_blocks_before_provider_execution(self):
        self.script.write_text(self.script.read_text()+'\n# changed')
        result=self.call('versions')
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(self.script.with_suffix('.calls').exists())
    def test_successful_submit_is_structured_and_does_not_grant_business_verdict(self):
        result=self.call('submit',execute=True)
        self.assertEqual(result['bug_id'],42)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(result['product_verdict'],'not_evaluated')
        args=json.loads(self.script.with_suffix('.calls').read_text())
        self.assertIn('--submit',args)
        self.assertEqual(args[args.index('--input')+1],str(self.issue.resolve()))
    def test_unconfirmed_or_other_run_candidate_never_calls_provider(self):
        for value in ({'run_id':'OTHER','candidates':[{'candidate_id':'C1','status':'confirmed_defect'}]}, {'run_id':'RUN1','candidates':[{'candidate_id':'C1','status':'candidate_issue'}]}):
            with self.subTest(value=value):
                self.triage.write_text(json.dumps(value))
                self.assertEqual(self.call('submit',execute=True)['status'],'blocked')
        self.assertFalse(self.script.with_suffix('.calls').exists())
    def test_unselected_versions_never_call_provider(self):
        self.run.write_text(json.dumps({'run_id':'RUN1','builds':[]}))
        self.assertEqual(self.call('submit',execute=True)['status'],'blocked')
        self.assertFalse(self.script.with_suffix('.calls').exists())
    def test_version_selection_preserves_execution_run_id(self):
        self.run.unlink()
        result=defects.run_adapter(self.config,'select',run=self.run,scope='Synthetic scope',builds=[7],confirmed_by='Reviewer',run_id='RUN-EXISTING')
        self.assertEqual(result['run_id'],'RUN-EXISTING')
        self.assertEqual(json.loads(self.run.read_text())['run_id'],'RUN-EXISTING')
    def test_provider_failure_is_not_echoed_or_reported_success(self):
        self.script.write_text('import sys\nprint("secret-password",file=sys.stderr)\nsys.exit(2)')
        defects.configure_adapter([sys.executable,str(self.script)],[],self.config)
        result=self.call('submit',execute=True)
        self.assertEqual(result['status'],'blocked')
        self.assertNotIn('secret-password',json.dumps(result))
    def test_failed_provider_replaces_stale_success_output(self):
        output=self.root/'receipt.json';output.write_text('{"status":"verified","bug_id":999}')
        self.script.write_text('import sys;sys.exit(2)')
        defects.configure_adapter([sys.executable,str(self.script)],[],self.config)
        result=self.call('submit',execute=True,output=output)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(json.loads(output.read_text())['status'],'blocked')
    def test_preflight_failure_replaces_stale_success_output(self):
        for reason in ('permission','source_drift','triage'):
            with self.subTest(reason=reason):
                output=self.root/'receipt.json';output.write_text('{"status":"verified","bug_id":999}')
                if reason=='source_drift':self.script.write_text(self.script.read_text()+'\n# drift')
                if reason=='triage':
                    defects.configure_adapter([sys.executable,str(self.script)],[],self.config)
                    self.triage.write_text('{"run_id":"OTHER","candidates":[]}')
                result=self.call('submit',execute=reason!='permission',output=output)
                self.assertEqual(result['status'],'blocked')
                self.assertEqual(json.loads(output.read_text())['status'],'blocked')
    def test_output_cannot_clobber_provider_receipt_or_browser_state(self):
        folder=Path(str(self.run)+'.receipts');folder.mkdir()
        for name in ('issue.json','issue.browser.json','issue.lock'):
            path=folder/name;path.write_text('{"status":"creating","marker":"preserve"}')
            result=self.call('submit',execute=True,output=path)
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(json.loads(path.read_text())['marker'],'preserve')
        self.assertFalse(self.script.with_suffix('.calls').exists())
    def test_malformed_nested_replies_return_structured_blocker(self):
        for action, reply in [('submit',{'status':'verified','bug_id':42,'evidence':None}),('versions',{'status':'needs_selection','versions':[None]})]:
            with self.subTest(action=action):
                self.script.write_text('import json;print(json.dumps('+repr(reply)+'))')
                defects.configure_adapter([sys.executable,str(self.script)],[],self.config)
                self.assertEqual(self.call(action,execute=True)['status'],'blocked')
    def test_exit_zero_with_unverified_reply_is_blocked(self):
        self.script.write_text('print(\'{"status":"created","bug_id":42}\')')
        defects.configure_adapter([sys.executable,str(self.script)],[],self.config)
        self.assertEqual(self.call('submit',execute=True)['status'],'blocked')
    def test_cli_entrypoint_dispatch_and_output(self):
        from ai_test_framework.cli import main
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            code=main(['defect-submit','--adapter',str(self.config),'--run',str(self.run),'--input',str(self.issue),'--execute','--output',str(self.root/'receipt.json')])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out.getvalue())['bug_id'],42)
        self.assertEqual(json.loads((self.root/'receipt.json').read_text())['status'],'verified')
    def test_output_cannot_overwrite_source_or_run(self):
        from ai_test_framework.cli import main
        with contextlib.redirect_stdout(io.StringIO()):
            code=main(['defect-submit','--adapter',str(self.config),'--run',str(self.run),'--input',str(self.issue),'--execute','--output',str(self.run)])
        self.assertNotEqual(code,0)
        self.assertFalse(self.script.with_suffix('.calls').exists())


class AdapterConfigDiscoveryTest(unittest.TestCase):
    def test_environment_config_is_resolved_without_explicit_flag(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'AI_TEST_DEFECT_ADAPTER':'/tmp/local-adapter.json'}):
            self.assertEqual(defects.resolve_adapter_config(),Path('/tmp/local-adapter.json').resolve())

if __name__=='__main__':unittest.main()
