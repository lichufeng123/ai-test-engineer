"""Controlled method catalogs and Case-level AI routing; never a model executor."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


STRATEGIES = {'deterministic', 'ai_assisted', 'hybrid_required', 'human_semantic_review'}
AUTHORITIES = {'deterministic_source', 'approved_semantic_gold', 'human_review_receipt'}
AI_AUTHORITIES = {'input_provider', 'advisory_only', 'evidence_reviewer', 'human_required'}
ROLES = {
    'semantic_answering': {'input_provider'},
    'answer_blueprint_rendering': {'input_provider'},
    'fixture_content_generation': {'input_provider'},
    'semantic_quality_review': {'evidence_reviewer', 'human_required'},
    'visual_observation': {'advisory_only', 'evidence_reviewer'},
    'navigation_advisory': {'advisory_only'},
    'diagnosis_and_repair_advisory': {'advisory_only'},
}
USAGES = {'product_outcome', 'semantic_quality', 'side_effect', 'authorization', 'state_persistence'}
DISPOSITIONS = {'reuse_existing_fixture', 'extend_fixture', 'build_testability_asset',
                'runtime_ai_required', 'manual_only_pending_oracle', 'not_applicable'}


def has_ai_contract(source):
    return (any(key in source for key in ('catalog_ref', 'ai_capabilities', 'oracle_resources',
                'testability_assessments', 'deterministic_fallbacks', 'resource_check_max_age_seconds'))
            or any(any(key in case for key in ('execution_strategy', 'ai_capability_bindings',
                                              'assertion_oracle_bindings'))
                   for case in source.get('case_requirements', [])))


def assertion_authorities(assertion):
    if assertion['required_conclusion_authority'] == 'composite':
        return set(assertion['composite_authorities'])
    return {assertion['required_conclusion_authority']}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def records(value, id_field, code):
    require(isinstance(value, list), code)
    result = {}
    for row in value:
        require(isinstance(row, dict) and text(row.get(id_field)), code)
        require(row[id_field] not in result, 'duplicate_' + code)
        result[row[id_field]] = row
    return result


def load_catalog(source, explicit_path=None, base=Path('.')):
    """Load bytes once; both explicit and source paths must designate one file."""
    ref = source.get('catalog_ref', {})
    declared = ref.get('path') if isinstance(ref, dict) else None
    require(explicit_path or declared, 'ai_catalog_required')
    declared_path = (base / declared).resolve() if declared else None
    path = Path(explicit_path).resolve() if explicit_path else declared_path
    require(not declared_path or path == declared_path, 'ai_catalog_path_conflict')
    try:
        raw = path.read_bytes()
        catalog = json.loads(raw)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError('ai_catalog_unreadable') from exc
    provenance = dict(path=str(path), catalog_id=catalog.get('catalog_id'),
                      sha256=hashlib.sha256(raw).hexdigest())
    if declared:
        provenance['path'] = declared
    return catalog, provenance


def validate_routing_plan(plan: Dict[str, Any], catalog, provenance):
    require(catalog is not None and provenance is not None, 'ai_catalog_required')
    require('ai_capabilities' not in plan, 'source_ai_definitions_forbidden')
    ref = plan.get('catalog_ref')
    require(isinstance(ref, dict) and text(ref.get('path')) and text(ref.get('catalog_id'))
            and sha(ref.get('sha256')) and ref == provenance, 'ai_catalog_provenance_mismatch')
    require(catalog.get('schema_version') == 1 and catalog.get('catalog_id') == ref['catalog_id'],
            'ai_catalog_identity_mismatch')
    capabilities = records(catalog.get('capabilities'), 'capability_id', 'ai_capability')
    for cap in capabilities.values():
        require(cap.get('conclusion_authority') in AI_AUTHORITIES, 'invalid_ai_authority')
        require(cap.get('role') in ROLES and cap['conclusion_authority'] in ROLES[cap['role']],
                'ai_role_authority_mismatch')
        require(all(text(cap.get(k)) for k in ['input_contract', 'output_contract', 'fallback_policy']),
                'ai_contract_required')
        require(type(cap.get('timeout_seconds')) is int and 0 < cap['timeout_seconds'] <= 3600,
                'ai_timeout_required')
        require(isinstance(cap.get('stop_conditions'), list) and cap['stop_conditions']
                and all(text(x) for x in cap['stop_conditions']), 'ai_stop_conditions_required')

    oracles = records(plan.get('oracle_resources'), 'oracle_id', 'oracle_resource')
    for oracle in oracles.values():
        require(oracle.get('kind') != 'input_fixture', 'input_fixture_not_oracle')
        require(oracle.get('kind') in AUTHORITIES and text(oracle.get('version'))
                and sha(oracle.get('sha256')) and text(oracle.get('independence_basis')),
                'oracle_contract_required')
    cases = records(plan['case_requirements'], 'case_id', 'case')
    referenced = set()
    assertion_ids = set()
    for case in cases.values():
        strategy = case.get('execution_strategy')
        require(strategy in STRATEGIES, 'execution_strategy_required')
        assertions = records(case.get('assertion_oracle_bindings'), 'assertion_id', 'assertion')
        require(bool(assertions), 'assertion_oracle_binding_required')
        for assertion in assertions.values():
            require(assertion['assertion_id'] not in assertion_ids, 'duplicate_assertion_id')
            assertion_ids.add(assertion['assertion_id'])
            authority = assertion.get('required_conclusion_authority')
            require(authority in AUTHORITIES | {'composite'}, 'invalid_conclusion_authority')
            required = assertion.get('composite_authorities', []) if authority == 'composite' else [authority]
            require(authority == 'composite' or 'composite_authorities' not in assertion,
                    'composite_field_requires_composite_authority')
            if authority == 'composite':
                require(isinstance(required, list) and len(required) >= 2
                        and len(set(required)) == len(required) and set(required) <= AUTHORITIES,
                        'composite_authorities_required')
            refs = assertion.get('oracle_refs')
            require(isinstance(refs, list) and refs and all(text(x) for x in refs)
                    and len(set(refs)) == len(refs), 'oracle_refs_required')
            require(set(refs) <= set(oracles), 'unknown_oracle_resource')
            require(set(required) <= {oracles[x]['kind'] for x in refs}, 'oracle_authority_mismatch')
            require(assertion.get('usage') in USAGES, 'oracle_usage_required')
            if assertion['usage'] == 'semantic_quality':
                require(bool(set(required) & {'approved_semantic_gold', 'human_review_receipt'}),
                        'semantic_oracle_required')
        bindings = records(case.get('ai_capability_bindings'), 'capability_id', 'ai_binding')
        require(set(bindings) <= set(capabilities), 'unknown_ai_capability')
        require(strategy != 'deterministic' or not bindings, 'deterministic_ai_binding_forbidden')
        require(strategy != 'hybrid_required' or any(b.get('necessity') == 'required' for b in bindings.values()),
                'hybrid_required_capability_missing')
        require(strategy != 'ai_assisted' or bool(bindings), 'ai_assisted_binding_missing')
        for binding in bindings.values():
            require(binding.get('necessity') in {'required', 'recommended', 'optional'}, 'invalid_ai_necessity')
            supported = binding.get('supports_assertion_ids', [])
            require(isinstance(supported, list) and set(supported) <= set(assertions), 'unknown_ai_assertion')
            require(binding['necessity'] == 'required' or not supported, 'nonrequired_ai_formal_assertion')
            cap = capabilities[binding['capability_id']]
            if cap['conclusion_authority'] == 'human_required':
                require(any('human_review_receipt' in assertion_authorities(a)
                            for a in assertions.values()), 'human_review_oracle_required')
            referenced.add(binding['capability_id'])
        if strategy == 'human_semantic_review':
            require(any(a['usage'] == 'semantic_quality' for a in assertions.values()), 'semantic_assertion_required')
    require(set(oracles) == {ref for c in cases.values() for a in c['assertion_oracle_bindings']
                            for ref in a['oracle_refs']}, 'unbound_oracle_resource')

    assessments = records(plan.get('testability_assessments'), 'assessment_id', 'testability_assessment')
    covered = set()
    for assessment in assessments.values():
        required_text = ['feature_id', 'basis', 'target_environment', 'cost_benefit', 'owner',
                         'freeze_and_drift', 'retention_cleanup', 'oracle_gap', 'next_step']
        require(all(text(assessment.get(k)) for k in required_text), 'testability_details_required')
        require(assessment.get('disposition') in DISPOSITIONS, 'testability_disposition_required')
        ids = assessment.get('case_ids')
        require(isinstance(ids, list) and ids and set(ids) <= set(cases), 'unknown_testability_case')
        for key in ['instability_sources', 'assets', 'prerequisites']:
            require(isinstance(assessment.get(key), list) and all(text(x) for x in assessment[key]),
                    'testability_details_required')
        covered.update(ids)
    require(covered == set(cases), 'testability_case_uncovered')
    age = plan.setdefault('resource_check_max_age_seconds', 300)
    require(type(age) is int and 0 < age <= 3600, 'resource_check_age_invalid')
    fallbacks = records(plan.get('deterministic_fallbacks', []), 'fallback_id', 'reference_fallback')
    pairs = set()
    for fallback in fallbacks.values():
        case = cases.get(fallback.get('case_id'), {})
        cap = capabilities.get(fallback.get('capability_id'), {})
        pair = (fallback.get('case_id'), fallback.get('capability_id'))
        require(pair not in pairs, 'duplicate_reference_fallback_binding')
        pairs.add(pair)
        require(fallback.get('kind') == 'approved_reference'
                and case.get('execution_strategy') == 'ai_assisted'
                and cap.get('role') == 'semantic_answering'
                and fallback.get('capability_id') in {b['capability_id'] for b in case.get('ai_capability_bindings', [])}
                and fallback.get('review_status') == 'approved_reference'
                and fallback.get('full_case_scope') is True
                and all(text(fallback.get(k)) for k in ['question_id', 'input_asset_id', 'version'])
                and all(sha(fallback.get(k)) for k in ['question_sha256', 'sha256']),
                'invalid_deterministic_fallback')
    plan['ai_capabilities'] = [copy.deepcopy(capabilities[k]) for k in sorted(referenced)]


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.timestamp() if result.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def fresh_check(check, confirmation, max_age):
    if not check:
        return False
    now = datetime.now(timezone.utc).timestamp()
    checked = timestamp(check.get('checked_at'))
    confirmed = timestamp(confirmation.get('confirmed_at'))
    return (checked is not None and confirmed is not None
            and 0 <= now - checked <= max_age and 0 <= now - confirmed <= max_age
            and check.get('status') == 'available' and text(check.get('evidence_ref'))
            and check.get('target_environment') == confirmation.get('target_environment'))


def evaluate_routing(plan, confirmation):
    """Evaluate attestations, retaining full Case/Oracle scope on every path."""
    # Revalidate frozen contracts too; callers need not have used the builder.
    source = copy.deepcopy(plan)
    frozen = source.pop('ai_capabilities', None)
    require(isinstance(frozen, list), 'frozen_ai_capabilities_required')
    validate_routing_plan(source, dict(schema_version=1, catalog_id=plan['catalog_ref']['catalog_id'],
                                      capabilities=frozen), plan['catalog_ref'])
    require(source['ai_capabilities'] == frozen, 'frozen_ai_capabilities_mismatch')
    capabilities = {c['capability_id']: c for c in frozen}
    oracles = {o['oracle_id']: o for o in plan['oracle_resources']}
    checks = records(confirmation.get('ai_capability_checks', []), 'capability_id', 'ai_check')
    oracle_checks = records(confirmation.get('oracle_resource_checks', []), 'oracle_id', 'oracle_check')
    references = records(confirmation.get('reference_answer_checks', []), 'fallback_id', 'reference_check')
    fallbacks = {f['fallback_id']: f for f in plan.get('deterministic_fallbacks', [])}
    require(set(checks) <= set(capabilities), 'unknown_ai_check')
    require(set(oracle_checks) <= set(oracles), 'unknown_oracle_check')
    require(set(references) <= set(fallbacks), 'unknown_reference_check')
    age = plan['resource_check_max_age_seconds']
    catalog_current = confirmation.get('catalog_sha256') == plan['catalog_ref']['sha256']
    ready_oracles = set()
    for oid, oracle in oracles.items():
        check = oracle_checks.get(oid)
        if (fresh_check(check, confirmation, age) and check.get('independent') is True
                and check.get('review_status') == 'approved'
                and all(check.get(k) == oracle[k] for k in ('version', 'sha256', 'kind'))
                and (oracle['kind'] == 'deterministic_source' or text(check.get('review_receipt_ref')))):
            ready_oracles.add(oid)
    warnings = []
    case_blocks = {}
    recommendations = []
    for case in plan['case_requirements']:
        cid = case['case_id']
        missing_ai = []
        used_references = []
        ai_roles = []
        for binding in case['ai_capability_bindings']:
            ident = binding['capability_id']
            cap = capabilities[ident]
            check = checks.get(ident)
            available = (catalog_current and fresh_check(check, confirmation, age)
                         and check.get('catalog_sha256') == plan['catalog_ref']['sha256'])
            ai_roles.append(dict(capability_id=ident, role=cap['role'],
                                 conclusion_authority=cap['conclusion_authority'],
                                 necessity=binding['necessity'], available=bool(available)))
            if available:
                continue
            fallback = next((f for f in fallbacks.values() if f['case_id'] == cid
                             and f['capability_id'] == ident), None)
            if fallback:
                observed = references.get(fallback['fallback_id'])
                if (fresh_check(observed, confirmation, age)
                        and all(observed.get(k) == v for k, v in fallback.items())):
                    used_references.append(fallback['fallback_id'])
                    continue
            if binding['necessity'] == 'required':
                missing_ai.append(ident)
            elif binding['necessity'] == 'recommended':
                warnings.append(dict(case_id=cid, capability_id=ident,
                                     reason='recommended_ai_unavailable', formal_scope_unchanged=True))
        required_oracles = {oid for a in case['assertion_oracle_bindings'] for oid in a['oracle_refs']}
        missing_oracles = sorted(required_oracles - ready_oracles)
        if missing_ai or missing_oracles:
            case_blocks[cid] = dict(missing_ai_capability_ids=sorted(missing_ai),
                                    missing_oracle_ids=missing_oracles)
        platforms = plan['automation_scope']['platforms']
        recommendations.append(dict(case_id=cid, execution_strategy=case['execution_strategy'],
            deterministic_executors=platforms, ai_responsibilities=ai_roles,
            assertion_oracle_bindings=copy.deepcopy(case['assertion_oracle_bindings']),
            deterministic_fallback_ids=used_references,
            conclusion_scope='full_declared_case_only; no runtime assertion trimming',
            recommendation=('按冻结用例执行；AI只提供声明的输入或建议，确定性执行器负责动作和状态回读；'
                            '正式断言仍须全部独立Oracle；缺少必需前置时阻塞整条用例。')))
    return dict(blocks=case_blocks, warnings=warnings, execution_recommendations=recommendations)


def merge_routing(plan, confirmation, ready, blocked, ledger, previous_missing):
    """Merge resource blocks into the existing readiness gate and retry ledger."""
    route = evaluate_routing(plan, confirmation)
    excluded = set(confirmation['excluded_case_ids']) | set(plan.get('manual_only_case_ids', []))
    previous = {item.get('prerequisite_fingerprint'): item for item in (previous_missing or [])}
    by_case = {b['case_id']: b for b in blocked}
    for cid, missing in route['blocks'].items():
        if cid in excluded:
            continue
        if cid in ready:
            ready.remove(cid)
        row = by_case.get(cid)
        if row is None:
            row = dict(case_id=cid, execution_action='skip_without_retry',
                       resume_condition='prerequisite_fingerprint_changed')
            blocked.append(row)
            by_case[cid] = row
        row.update(missing)
        fingerprint = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        old = previous.get(fingerprint)
        ledger[:] = [item for item in ledger if item['case_id'] != cid]
        ledger.append(copy.deepcopy(old) if old else dict(
            case_id=cid, prerequisite_fingerprint=fingerprint, **missing,
            first_detected_at=confirmation.get('confirmed_at'), retry_count=0,
            retry_allowed=False, next_action='await_prerequisite'))
    return {key: route[key] for key in ('warnings', 'execution_recommendations')}

