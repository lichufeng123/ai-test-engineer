import copy
import hashlib
import json
import unittest
import tempfile
import contextlib
import io
from pathlib import Path
from datetime import datetime, timezone, timedelta

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


def confirmed_v2(plan, **overrides):
    now = datetime.now(timezone.utc).isoformat()
    value = confirmation(plan, schema_version=2, confirmed_at=now,
        ready_fixture_ids=['unassigned_recording'], catalog_sha256=SHA,
        ai_capability_checks=[], oracle_resource_checks=[{
            'oracle_id': 'state-source', 'version': '1', 'sha256': SHA,
            'kind': 'deterministic_source', 'status': 'available',
            'review_status': 'approved', 'independent': True,
            'checked_at': now, 'target_environment': 'sit', 'evidence_ref': 'audit-check.json'}])
    value.update(overrides)
    return value


def ai_check(**overrides):
    return dict(capability_id='dialogue-answer', status='available',
                checked_at=datetime.now(timezone.utc).isoformat(), target_environment='sit',
                catalog_sha256=SHA, evidence_ref='answer-handoff-precheck.json', **overrides)


class RoutingGateTest(unittest.TestCase):
    def test_execution_entry_rejects_downgraded_v2_contract(self):
        p=freeze(); p['schema_version']=1
        c=confirmed_v2(p,schema_version=1,ai_capability_checks=[],oracle_resource_checks=[])
        r=evaluate_execution_readiness(p,c)
        self.assertEqual(r['ready_case_ids'],[])
        self.assertIn('ai_contract_requires_v2',r['error_codes'])

    def test_inactive_composite_field_cannot_satisfy_human_requirement(self):
        s=source_v2(); cat=catalog(); cat['capabilities'][0].update(
            role='semantic_quality_review',conclusion_authority='human_required')
        s['case_requirements'][1]['assertion_oracle_bindings'][0]['composite_authorities']=[
            'deterministic_source','human_review_receipt']
        with self.assertRaisesRegex(ValueError,'composite_field_requires_composite_authority'):
            freeze(s,cat=cat)

    def test_wrong_confirmation_version_and_catalog_drift_fail_closed(self):
        p=freeze()
        for patch,code in [({'schema_version':1},'confirmation_schema_mismatch'),
                           ({'catalog_sha256':'b'*64},'ai_catalog_hash_mismatch')]:
            c=confirmed_v2(p,**patch); r=evaluate_execution_readiness(p,c)
            self.assertEqual(r['ready_case_ids'],[])
            self.assertIn(code,r['error_codes'])

    def test_required_missing_only_blocks_dependent_case(self):
        p = freeze(); result = evaluate_execution_readiness(p, confirmed_v2(p))
        self.assertEqual(result['ready_case_ids'], ['TC-001'])
        self.assertEqual(result['blocked_cases'][0]['missing_ai_capability_ids'], ['dialogue-answer'])
        self.assertEqual(result['execution_recommendations'][1]['execution_strategy'], 'hybrid_required')

    def test_available_check_unblocks_without_model_invocation(self):
        p = freeze(); r = evaluate_execution_readiness(p, confirmed_v2(p, ai_capability_checks=[ai_check()]))
        self.assertEqual(r['ready_case_ids'], ['TC-001', 'TC-002'])

    def test_missing_recommended_and_optional_are_not_formal_scope_reduction(self):
        for necessity in ['recommended', 'optional']:
            s = source_v2(); s['case_requirements'][1]['execution_strategy'] = 'ai_assisted'
            s['case_requirements'][1]['ai_capability_bindings'][0]['necessity'] = necessity
            p = freeze(s); r = evaluate_execution_readiness(p, confirmed_v2(p))
            self.assertEqual(r['ready_case_ids'], ['TC-001', 'TC-002'])
            self.assertEqual(len(r['execution_recommendations'][1]['assertion_oracle_bindings']), 1)
            self.assertEqual(bool(r['warnings']), necessity == 'recommended')

    def test_configured_state_does_not_prove_current_availability(self):
        c = catalog(); c['capabilities'][0]['configured'] = True
        p = freeze(cat=c)
        self.assertEqual(evaluate_execution_readiness(p, confirmed_v2(p))['ready_case_ids'], ['TC-001'])

    def test_stale_evidence_wrong_environment_hash_or_missing_evidence_block(self):
        for patch in [
            {'checked_at': (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()},
            {'checked_at': (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()},
            {'target_environment': 'other'}, {'catalog_sha256': 'b'*64}, {'evidence_ref': ''},
            {'status': 'unknown'}, {'status': 'unavailable'}]:
            check = ai_check(); check.update(patch); p = freeze()
            r = evaluate_execution_readiness(p, confirmed_v2(p, ai_capability_checks=[check]))
            self.assertEqual(r['ready_case_ids'], ['TC-001'], patch)

    def test_duplicate_or_unknown_checks_rejected(self):
        p = freeze(); check = ai_check()
        with self.assertRaisesRegex(ValueError, 'duplicate_ai_check'):
            evaluate_execution_readiness(p, confirmed_v2(p, ai_capability_checks=[check, check]))
        check['capability_id'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unknown_ai_check'):
            evaluate_execution_readiness(p, confirmed_v2(p, ai_capability_checks=[check]))

    def test_model_available_never_replaces_oracle(self):
        p = freeze(); r = evaluate_execution_readiness(p, confirmed_v2(p,
            ai_capability_checks=[ai_check()], oracle_resource_checks=[]))
        self.assertEqual(r['ready_case_ids'], [])
        self.assertTrue(all(b['missing_oracle_ids'] == ['state-source'] for b in r['blocked_cases']))

    def test_oracle_identity_review_and_independence_must_all_match(self):
        p = freeze()
        for patch in [{'version':'2'}, {'sha256':'b'*64}, {'independent':False},
                      {'review_status':'pending'}, {'status':'unknown'}, {'kind':'input_fixture'}]:
            c = confirmed_v2(p, ai_capability_checks=[ai_check()]); c['oracle_resource_checks'][0].update(patch)
            self.assertEqual(evaluate_execution_readiness(p,c)['ready_case_ids'], [], patch)

    def test_same_missing_ai_prerequisite_is_not_retried(self):
        p = freeze(); c = confirmed_v2(p); r = evaluate_execution_readiness(p, c)
        again = evaluate_execution_readiness(p, c, previous_missing=r['missing_prerequisites'])
        self.assertEqual(r['missing_prerequisites'], again['missing_prerequisites'])
        self.assertFalse(again['missing_prerequisites'][0]['retry_allowed'])

    def test_semantic_composite_requires_gold_and_human_receipt(self):
        s = source_v2(); case = s['case_requirements'][1]
        case['execution_strategy'] = 'human_semantic_review'
        s['oracle_resources'] += [
            {'oracle_id':kind,'kind':kind,'version':'1','sha256':SHA,'independence_basis':'independent reviewed source'}
            for kind in ['approved_semantic_gold','human_review_receipt']]
        case['assertion_oracle_bindings'] = [{
            'assertion_id':'SEMANTIC-1','usage':'semantic_quality','required_conclusion_authority':'composite',
            'composite_authorities':['approved_semantic_gold','human_review_receipt'],
            'oracle_refs':['approved_semantic_gold','human_review_receipt']}]
        p = freeze(s); c = confirmed_v2(p, ai_capability_checks=[ai_check()]); now=c['confirmed_at']
        for kind in ['approved_semantic_gold','human_review_receipt']:
            c['oracle_resource_checks'].append(dict(oracle_id=kind,kind=kind,version='1',sha256=SHA,
                status='available',review_status='approved',independent=True,checked_at=now,
                target_environment='sit',evidence_ref='semantic-audit.json',review_receipt_ref='reviewed.json'))
        self.assertEqual(evaluate_execution_readiness(p,c)['ready_case_ids'], ['TC-001','TC-002'])
        del c['oracle_resource_checks'][-1]['review_receipt_ref']
        self.assertEqual(evaluate_execution_readiness(p,c)['ready_case_ids'], ['TC-001'])

    def test_preapproved_child_case_stays_independent_and_parent_not_trimmed(self):
        p = freeze(); r=evaluate_execution_readiness(p,confirmed_v2(p))
        self.assertEqual(r['ready_case_ids'],['TC-001'])
        self.assertEqual([b['case_id'] for b in r['blocked_cases']],['TC-002'])
        self.assertEqual(p['automation_scope']['case_ids'],['TC-001','TC-002'])

    def test_reviewed_reference_allows_full_scope_deterministic_fallback(self):
        s=source_v2(); s['case_requirements'][1]['execution_strategy']='ai_assisted'
        s['deterministic_fallbacks']=[{
            'fallback_id':'REF-1','case_id':'TC-002','capability_id':'dialogue-answer',
            'kind':'approved_reference','question_id':'Q1','question_sha256':SHA,
            'input_asset_id':'ANSWER-1','version':'1','sha256':SHA,
            'review_status':'approved_reference','full_case_scope':True}]
        p=freeze(s); check={**s['deterministic_fallbacks'][0], 'status':'available',
            'checked_at':datetime.now(timezone.utc).isoformat(),'target_environment':'sit',
            'evidence_ref':'question-id-and-hash-check.json'}
        c=confirmed_v2(p,reference_answer_checks=[check])
        r=evaluate_execution_readiness(p,c)
        self.assertEqual(r['ready_case_ids'],['TC-001','TC-002'])
        self.assertEqual(r['execution_recommendations'][1]['deterministic_fallback_ids'],['REF-1'])
        check['question_sha256']='b'*64
        self.assertEqual(evaluate_execution_readiness(p,c)['ready_case_ids'],['TC-001'])

    def test_blueprint_and_hybrid_case_cannot_remove_runtime_ai_requirement(self):
        s=source_v2(); s['deterministic_fallbacks']=[{'fallback_id':'bad','case_id':'TC-002',
            'capability_id':'dialogue-answer','kind':'answer_blueprint'}]
        with self.assertRaisesRegex(ValueError,'invalid_deterministic_fallback'):
            freeze(s)


class RoutingCliTest(unittest.TestCase):
    def test_shipped_catalog_example_and_v2_template_are_consistent(self):
        from ai_test_framework.cli import main
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'plan.json'
            with contextlib.redirect_stdout(io.StringIO()):
                main(['readiness-plan','--input',str(root/'templates/automation-readiness-v2.example.json'),
                      '--output',str(out)])
            p=json.loads(out.read_text())
            self.assertEqual(p['schema_version'],2)
            self.assertEqual({x['execution_strategy'] for x in p['case_requirements']},
                             {'deterministic','hybrid_required'})
        for path in ['schemas/ai-test-capability-catalog.schema.json',
                     'docs/AI_ASSISTED_TESTING_ROUTING.zh-CN.md']:
            self.assertTrue((root/path).is_file(),path)

    def test_catalog_loaded_relative_to_source_and_drift_detected_before_execution(self):
        from ai_test_framework.cli import main
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); cat=base/'catalog.json'; cat.write_text(json.dumps(catalog()))
            s=source_v2(); s['catalog_ref']['sha256']=hashlib.sha256(cat.read_bytes()).hexdigest()
            src=base/'source.json'; src.write_text(json.dumps(s)); out=base/'different'/'plan.json'
            with contextlib.redirect_stdout(io.StringIO()):
                main(['readiness-plan','--input',str(src),'--output',str(out)])
            p=json.loads(out.read_text())
            self.assertEqual(p['catalog_ref']['path'],str(cat.resolve()))
            check=confirmed_v2(p); check['catalog_sha256']=p['catalog_ref']['sha256']
            conf=base/'confirmation.json'; conf.write_text(json.dumps(check)); result=base/'result.json'
            cat.write_text(cat.read_text()+'\n')
            with contextlib.redirect_stdout(io.StringIO()):
                main(['readiness-check','--plan',str(out),'--confirmation',str(conf),'--output',str(result)])
            self.assertIn('ai_catalog_hash_mismatch',json.loads(result.read_text())['error_codes'])

    def test_explicit_catalog_must_not_hide_source_hash_mismatch(self):
        from ai_test_framework.cli import main
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); cat=base/'catalog.json'; cat.write_text(json.dumps(catalog()))
            src=base/'source.json'; src.write_text(json.dumps(source_v2()))
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError,'ai_catalog_provenance_mismatch'):
                main(['readiness-plan','--input',str(src),'--ai-capability-catalog',str(cat),'--output',str(base/'plan.json')])


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
