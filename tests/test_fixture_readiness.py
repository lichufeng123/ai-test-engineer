import unittest
from test_execution_readiness import readiness_source
from ai_test_framework.execution_readiness import build_readiness_plan,evaluate_execution_readiness

class ManagedReadinessTests(unittest.TestCase):
    def test_missing_registry_blocks_only_declared_case(self):
        source=readiness_source()
        source['business_fixture_needs']=[dict(requirement_id='REQ-BADGE-001',case_id='TC-001',fixture_key='member.smoke',version='1',usage='read')]
        source['business_fixture_target_refs']={'sit':'sit-shop'}
        plan=build_readiness_plan(source)
        confirmation=dict(schema_version=1,plan_id=plan['plan_id'],plan_sha256=plan['plan_sha256'],target_environment='sit',
            scope_confirmed=True,environment_confirmed=True,account_roles_confirmed=True,data_plan_confirmed=True,
            available_role_ids=['store_admin'],ready_fixture_ids=['unassigned_recording'],excluded_case_ids=[])
        result=evaluate_execution_readiness(plan,confirmation)
        self.assertEqual(result['ready_case_ids'],['TC-002'])
        self.assertEqual(result['fixture_resource_checks'][0]['fixture_status'],'blocked')

    def test_unknown_case_cannot_be_silently_ignored(self):
        source=readiness_source();source['business_fixture_needs']=[dict(requirement_id='REQ-BADGE-001',case_id='UNKNOWN',fixture_key='member.smoke',version='1',usage='read')]
        source['business_fixture_target_refs']={'sit':'sit-shop'}
        with self.assertRaises(ValueError):build_readiness_plan(source)
