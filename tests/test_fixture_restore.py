import tempfile,time,unittest
from pathlib import Path
from ai_test_framework.fixtures.registry import Registry,FixtureError
class RestoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Registry(Path(self.tmp.name)/'db')
  self.target=dict(target_ref='sit',stage='sit',zone='z1',organization='4',salon='21',role='employee',platform='api',build='contract')
  self.r.add_target(self.target);self.r.add_blueprints([dict(fixture_key='goal',version='1',entity='goal',pool='run',attributes={'quantity':1},requires=[])])
  self.r.bind('goal','1','sit','50');self.r.observe('goal','1','sit',self.obs())
 def obs(self,quantity=1):return dict(local_id='50',target=self.target,attributes={'quantity':quantity},observed_at=time.time(),evidence_ref='independent-native+consumer')
 def write(self):
  lease=self.r.acquire([dict(fixture_key='goal',version='1',target_ref='sit',mode='write')],'RUN')
  self.r.release(lease['lease_id'],'RUN',{'50':self.obs()});return lease['lease_id']
 def test_owned_released_writer_can_reconcile_exact_restored_snapshot(self):
  lid=self.write()
  with self.assertRaises(FixtureError):self.r.resolve('goal','1','sit')
  result=self.r.restore_consumed('goal','1','sit',lid,'RUN',self.obs())
  self.assertEqual(result['status'],'healthy');self.assertEqual(self.r.resolve('goal','1','sit')['local_id'],'50')
 def test_wrong_owner_changed_snapshot_and_unreleased_lease_stay_blocked(self):
  lid=self.write()
  for owner,obs in [('OTHER',self.obs()),('RUN',self.obs(2))]:
   with self.assertRaises(FixtureError):self.r.restore_consumed('goal','1','sit',lid,owner,obs)
  self.r.restore_consumed('goal','1','sit',lid,'RUN',self.obs())
  active=self.r.acquire([dict(fixture_key='goal',version='1',target_ref='sit',mode='write')],'RUN')
  with self.assertRaises(FixtureError):self.r.restore_consumed('goal','1','sit',active['lease_id'],'RUN',self.obs())
 def test_old_write_lease_cannot_clear_later_consumption(self):
  old=self.write();self.r.restore_consumed('goal','1','sit',old,'RUN',self.obs());new=self.write()
  with self.assertRaises(FixtureError):self.r.restore_consumed('goal','1','sit',old,'RUN',self.obs())
  self.r.restore_consumed('goal','1','sit',new,'RUN',self.obs())
 def test_replay_quarantine_and_aliases_require_separate_reconciliation(self):
  stale=self.obs();lid=self.write()
  with self.assertRaises(FixtureError):self.r.restore_consumed('goal','1','sit',lid,'RUN',stale)
  self.r.add_blueprints([dict(fixture_key='alias',version='1',entity='goal',pool='run',attributes={'quantity':1},requires=[])])
  self.r.bind('alias','1','sit','50')
  with self.assertRaises(FixtureError):self.r.restore_consumed('goal','1','sit',lid,'RUN',self.obs())
