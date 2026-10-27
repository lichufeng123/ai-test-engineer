import copy
import hashlib
import json
import unittest

from test_execution_readiness import readiness_source, confirmation
from ai_test_framework.execution_readiness import build_readiness_plan, evaluate_execution_readiness


SHA = 'a' * 64
PROVENANCE = {'path': 'catalog.json', 'catalog_id': 'METHODS', 'sha256': SHA}


def catalog():
    return {'schema_version': 1, 'catalog_id': 'METHODS', 'capabilities': [{
        'capability_id': 'dialogue-answer', 'role': 'semantic_answering',
        'input_contract': 'same question and request identity',
        'output_contract': 'scoped answer through existing one-use handoff',
        'conclusion_authority': 'input_provider', 'timeout_seconds': 90,
        'stop_conditions': ['timeout', 'identity mismatch'],
        'fallback_policy': 'block dependent case',
    }]}


def source_v2():
    s = readiness_source()
    s.update(schema_version=2, catalog_ref=copy.deepcopy(PROVENANCE),
             resource_check_max_age_seconds=300,
             oracle_resources=[{'oracle_id': 'state-source', 'version': '1', 'sha256': SHA,
                                'kind': 'deterministic_source',
                                'independence_basis': 'independent event audit, not model output'}],
             testability_assessments=[{
                 'assessment_id': 'TA-1', 'feature_id': 'dialogue',
                 'case_ids': ['TC-001', 'TC-002'], 'instability_sources': ['generated questions'],
                 'disposition': 'runtime_ai_required', 'basis': 'reviewed dynamic dialogue goal',
                 'assets': ['dedicated scene and versioned blueprint'], 'target_environment': 'sit',
                 'cost_benefit': 'reusable regression, bounded maintenance',
                 'prerequisites': ['isolated fixture'], 'owner': 'owner_pending',
                 'freeze_and_drift': 'stable id, version, hash before action',
                 'retention_cleanup': 'retain dedicated scene, expire sessions',
                 'oracle_gap': 'semantic gold pending; state-only case scope',
                 'next_step': 'prepare reviewed input and independent audit',
             }])
    for case in s['case_requirements']:
        case.update(execution_strategy='deterministic', ai_capability_bindings=[],
                    assertion_oracle_bindings=[{
                        'assertion_id': case['case_id'] + '-STATE',
                        'required_conclusion_authority': 'deterministic_source',
                        'oracle_refs': ['state-source'], 'usage': 'state_persistence',
                    }])
    s['case_requirements'][1].update(execution_strategy='hybrid_required',
        ai_capability_bindings=[{'capability_id': 'dialogue-answer', 'necessity': 'required'}])
    return s


def freeze(source=None, cat=None, provenance=None):
    return build_readiness_plan(source or source_v2(), ai_capability_catalog=cat or catalog(),
                                catalog_provenance=provenance or PROVENANCE)


class RoutingContractTest(unittest.TestCase):
    def test_v1_no_model_required_even_feature_name_contains_ai(self):
        s = readiness_source(); s['feature'] = 'AI intelligent CRUD'
        p = build_readiness_plan(s)
        self.assertEqual(evaluate_execution_readiness(p, confirmation(p))['ready_case_ids'], ['TC-001'])

    def test_v2_freezes_catalog_and_does_not_mutate_source(self):
        s = source_v2(); before = copy.deepcopy(s); p = freeze(s)
        self.assertEqual(s, before)
        self.assertEqual(p['ai_capabilities'], catalog()['capabilities'])
        self.assertEqual(p['catalog_ref'], PROVENANCE)

    def test_v2_missing_catalog_and_hash_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ai_catalog_required'):
            build_readiness_plan(source_v2())
        with self.assertRaisesRegex(ValueError, 'ai_catalog_provenance_mismatch'):
            freeze(provenance={**PROVENANCE, 'sha256': 'b' * 64})

    def test_duplicate_and_unknown_capability_rejected(self):
        c = catalog(); c['capabilities'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate_ai_capability'):
            freeze(cat=c)
        s = source_v2(); s['case_requirements'][1]['ai_capability_bindings'][0]['capability_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'unknown_ai_capability'):
            freeze(s)

    def test_duplicate_binding_rejected_and_global_catalog_is_scoped(self):
        s = source_v2(); s['case_requirements'][1]['ai_capability_bindings'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate_ai_binding'):
            freeze(s)
        c = catalog(); c['capabilities'].append({**c['capabilities'][0], 'capability_id': 'unused'})
        self.assertEqual([a['capability_id'] for a in freeze(cat=c)['ai_capabilities']], ['dialogue-answer'])
        s = source_v2(); s['ai_capabilities'] = [c['capabilities'][1]]
        with self.assertRaisesRegex(ValueError, 'source_ai_definitions_forbidden'):
            freeze(s)

    def test_case_strategy_and_assessment_coverage_required(self):
        s = source_v2(); del s['case_requirements'][0]['execution_strategy']
        with self.assertRaisesRegex(ValueError, 'execution_strategy_required'):
            freeze(s)
        s = source_v2(); s['testability_assessments'][0]['case_ids'] = ['TC-001']
        with self.assertRaisesRegex(ValueError, 'testability_case_uncovered'):
            freeze(s)

    def test_permanent_manual_only_requires_testability_reasoning(self):
        s = source_v2(); s['manual_only_case_ids'] = ['TC-002']; s['testability_assessments'] = []
        with self.assertRaisesRegex(ValueError, 'testability_case_uncovered'):
            freeze(s)

    def test_ai_cannot_be_sole_oracle_or_escalate_authority(self):
        c = catalog(); c['capabilities'][0]['conclusion_authority'] = 'formal_judge'
        with self.assertRaisesRegex(ValueError, 'invalid_ai_authority'):
            freeze(cat=c)
        s = source_v2(); s['case_requirements'][0]['assertion_oracle_bindings'][0]['oracle_refs'] = ['dialogue-answer']
        with self.assertRaisesRegex(ValueError, 'unknown_oracle_resource'):
            freeze(s)

    def test_input_fixture_cannot_prove_product_or_semantic_quality(self):
        s = source_v2(); s['oracle_resources'][0]['kind'] = 'input_fixture'
        s['case_requirements'][0]['assertion_oracle_bindings'][0]['usage'] = 'product_outcome'
        with self.assertRaisesRegex(ValueError, 'input_fixture_not_oracle'):
            freeze(s)

    def test_recommended_cannot_support_formal_assertion(self):
        s = source_v2(); c = s['case_requirements'][1]; c['execution_strategy'] = 'ai_assisted'
        c['ai_capability_bindings'][0].update(necessity='recommended', supports_assertion_ids=['TC-002-STATE'])
        with self.assertRaisesRegex(ValueError, 'nonrequired_ai_formal_assertion'):
            freeze(s)

    def test_composite_requires_two_distinct_authorities(self):
        s = source_v2(); a = s['case_requirements'][1]['assertion_oracle_bindings'][0]
        a.update(required_conclusion_authority='composite', composite_authorities=['deterministic_source'])
        with self.assertRaisesRegex(ValueError, 'composite_authorities_required'):
            freeze(s)

    def test_v1_cannot_hide_v2_ai_fields(self):
        s = source_v2(); s['schema_version'] = 1
        with self.assertRaisesRegex(ValueError, 'ai_contract_requires_v2'):
            build_readiness_plan(s)


if __name__ == '__main__':
    unittest.main()
