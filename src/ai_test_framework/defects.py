"""Optional, hash-pinned tracker CLI integration; never infers a product verdict."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Dict, List

ACTIONS = ('versions', 'select', 'draft', 'submit', 'verify')


class DefectAdapterError(ValueError):
    pass


def _read(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise DefectAdapterError('invalid_json_object')
    return value


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _safe(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if re.fullmatch(r'(?i)(password|passwd|.*token|cookie|authorization|secret|api_key|zentaosid)', key):
                raise DefectAdapterError('sensitive_field_in_artifact')
            _safe(child)
    elif isinstance(value, list):
        for child in value:
            _safe(child)
    elif isinstance(value, str) and re.search(r'(?i)(zentaosid=|bearer\s+[a-z0-9._-]{8,})', value):
        raise DefectAdapterError('sensitive_value_in_artifact')


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            os.chmod(temp, 0o600)
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def configure_adapter(command: List[str], assets: List[str], output: Path) -> Dict[str, Any]:
    """Pin an explicitly chosen local command and its code dependencies, not credentials."""
    if not command or any(not Path(x).is_absolute() or not Path(x).is_file() for x in command):
        raise DefectAdapterError('command_requires_absolute_file_paths')
    paths = list(dict.fromkeys(str(Path(x).resolve()) for x in [*command, *assets]))
    if not os.access(command[0], os.X_OK):
        raise DefectAdapterError('adapter_not_executable')
    if Path(output).resolve() in [Path(x) for x in paths]:
        raise DefectAdapterError('output_would_overwrite_adapter')
    value = {'schema_version': 1, 'protocol': 'defect-cli-v1',
             'command': [str(Path(x).resolve()) for x in command],
             'assets': [{'path': x, 'sha256': _sha(x)} for x in paths]}
    _save(output, value)
    return {'status': 'configured', 'protocol': value['protocol'], 'asset_count': len(paths)}


def _configuration(path):
    value = _read(path)
    _safe(value)
    if value.get('schema_version') != 1 or value.get('protocol') != 'defect-cli-v1':
        raise DefectAdapterError('unsupported_adapter_protocol')
    command, assets = value.get('command'), value.get('assets')
    if not isinstance(command, list) or not command or not isinstance(assets, list):
        raise DefectAdapterError('adapter_configuration_invalid')
    registered = {}
    for asset in assets:
        p = Path(asset['path'])
        if not p.is_absolute() or str(p.resolve()) != asset['path'] or _sha(p) != asset['sha256']:
            raise DefectAdapterError('adapter_asset_changed')
        registered[str(p)] = asset['sha256']
    if any(not isinstance(x, str) or not Path(x).is_absolute() or x not in registered for x in command):
        raise DefectAdapterError('command_not_pinned')
    return value


def _input_context(run, issue, action):
    selected = _read(run)
    source = _read(issue)
    _safe(selected)
    _safe(source)
    if (not selected.get('run_id') or not selected.get('scope')
            or not selected.get('confirmed_by') or not selected.get('builds')):
        raise DefectAdapterError('version_selection_required')
    if action == 'submit':
        if source.get('source') != 'automation' or not source.get('triage_file') or not source.get('candidate_id'):
            raise DefectAdapterError('confirmed_automation_triage_required')
        triage = _read(Path(issue).parent / source['triage_file'])
        _safe(triage)
        rows=triage.get('candidates',[])
        if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):
            raise DefectAdapterError('invalid_triage_candidates')
        matches = [x for x in rows if x.get('candidate_id') == source['candidate_id']]
        if (triage.get('run_id') != selected['run_id'] or len(matches) != 1
                or matches[0].get('status') != 'confirmed_defect'):
            raise DefectAdapterError('candidate_unconfirmed_or_run_mismatch')
        # The provider must additionally execute its authoritative triage/evidence gates.
    return selected, source


def _protect_output(config_path, run, issue, output):
    if not output:
        return False
    target=Path(output).resolve()
    if target.suffix.lower()!='.json':
        raise DefectAdapterError('receipt_output_must_be_json')
    protected=[Path(p).resolve() for p in (config_path,run,issue) if p]
    if run and target.is_relative_to(Path(str(run)+'.receipts').resolve()):
        raise DefectAdapterError('output_is_provider_owned_state')
    # Read declared dependencies even when their hashes or authorization later fail.
    if Path(config_path).is_file():
        raw=_read(config_path)
        for row in raw.get('assets',[]):
            if isinstance(row,dict) and isinstance(row.get('path'),str):
                protected.append(Path(row['path']).resolve())
    if issue and Path(issue).is_file():
        raw=_read(issue)
        refs=[]
        for key in ('images','videos'):
            if isinstance(raw.get(key),list):
                refs += [x for x in raw[key] if isinstance(x,str)]
        if isinstance(raw.get('triage_file'),str):
            refs.append(raw['triage_file'])
        protected += [(Path(issue).parent/ref).resolve() for ref in refs]
    if target in protected:
        raise DefectAdapterError('output_would_overwrite_input_or_evidence')
    return True


def resolve_adapter_config(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured=os.environ.get('AI_TEST_DEFECT_ADAPTER')
    if configured:
        return Path(configured).expanduser().resolve()
    local=Path.cwd()/'.ai-test/defect-adapter.json'
    if local.is_file():
        return local
    return Path.home()/'.config/ai-test/defect-adapter.json'


def run_adapter(config_path, action, *, run=None, issue=None, scope=None, builds=None,
                confirmed_by=None, run_id=None, execute=False, output=None,
                resume_bug_id=None, timeout=600):
    """Execute one named adapter action, once. Fail closed; preserve provider receipts."""
    output_allowed=False
    try:
        config_path = resolve_adapter_config(config_path)
        output_allowed = _protect_output(config_path,run,issue,output)
        if action not in ACTIONS:
            raise DefectAdapterError('unknown_adapter_action')
        if action == 'submit' and execute is not True:
            raise DefectAdapterError('explicit_execute_required')
        config_path = resolve_adapter_config(config_path)
        config = _configuration(config_path)
        protected = [Path(config_path).resolve(), *(Path(x['path']) for x in config['assets'])]
        for path in (run, issue):
            if path:
                protected.append(Path(path).resolve())
        if output and Path(output).resolve() in protected:
            raise DefectAdapterError('output_would_overwrite_input')
        command = list(config['command']) + [action]
        if action == 'select':
            if not run or not scope or not builds or not confirmed_by or not run_id:
                raise DefectAdapterError('human_version_selection_and_execution_run_id_required')
            command += ['--run', str(Path(run).resolve()), '--scope', scope,
                        '--confirmed-by', confirmed_by, '--run-id', run_id]
            for build in builds:
                command += ['--build', str(int(build))]
        elif action in ('draft', 'submit', 'verify'):
            if not run or not issue:
                raise DefectAdapterError('input_and_run_required')
            selected, source = _input_context(run, issue, action)
            if output:
                evidence_paths = [Path(issue).parent / p for key in ('images', 'videos') for p in source.get(key, [])]
                if source.get('triage_file'):
                    evidence_paths.append(Path(issue).parent / source['triage_file'])
                if Path(output).resolve() in [p.resolve() for p in evidence_paths]:
                    raise DefectAdapterError('output_would_overwrite_evidence')
            command += ['--input', str(Path(issue).resolve()), '--run', str(Path(run).resolve())]
            if action == 'submit':
                command.append('--submit')
                if resume_bug_id is not None:
                    command += ['--resume-bug-id', str(int(resume_bug_id))]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise DefectAdapterError('adapter_timeout_unknown_state_resume_only') from None
        if process.returncode != 0:
            raise DefectAdapterError('provider_failed_check_private_receipt')
        try:
            result = json.loads(process.stdout)
        except ValueError:
            raise DefectAdapterError('provider_protocol_invalid_json') from None
        if not isinstance(result, dict):
            raise DefectAdapterError('provider_protocol_invalid_object')
        _safe(result)
        if action == 'versions':
            rows = result.get('versions')
            if result.get('status') != 'needs_selection' or not isinstance(rows, list) or len(rows) > 3:
                raise DefectAdapterError('provider_version_reply_invalid')
            if any(not isinstance(r,dict) or not isinstance(r.get('name'),str) or not isinstance(r.get('id'),(int,str)) for r in rows):
                raise DefectAdapterError('provider_version_row_invalid')
            result = {'status': 'needs_selection', 'versions': [
                {'id': r['id'], 'name': r['name'], 'created_at': r.get('createdDate', r.get('created_at'))} for r in rows]}
        elif action == 'select':
            stored = _read(run)
            if (result != stored or stored.get('run_id') != run_id
                    or stored.get('scope') != scope or stored.get('confirmed_by') != confirmed_by
                    or sorted(int(b['id']) for b in stored.get('builds', [])) != sorted(set(builds))):
                raise DefectAdapterError('provider_selection_readback_mismatch')
            result = {'status': 'selected', 'run_id': run_id, 'scope': scope,
                      'builds': stored['builds'], 'confirmed_by': confirmed_by}
        elif action == 'draft':
            if result.get('status') != 'draft':
                raise DefectAdapterError('provider_draft_reply_invalid')
        else:
            if (result.get('status') != 'verified' or type(result.get('bug_id')) is not int
                    or result['bug_id'] < 1 or not isinstance(result.get('evidence'),dict)
                    or result['evidence'].get('verified') is not True):
                raise DefectAdapterError('provider_submission_not_verified')
        result['product_verdict'] = 'not_evaluated'
        result['adapter_protocol'] = 'defect-cli-v1'
        if output:
            _save(output, result)
        return result
    except (OSError, ValueError, KeyError, TypeError):
        import sys
        error = sys.exc_info()[1]
        result = {'status': 'blocked', 'product_verdict': 'not_evaluated',
                  'error_codes': [str(error) if isinstance(error, DefectAdapterError) else 'adapter_input_or_runtime_invalid'],
                  'retry_policy': 'inspect_existing_provider_receipt_before_retry'}
        if output and output_allowed:
            try:
                _save(output,result)
            except OSError:
                result['error_codes'].append('receipt_output_unwritable')
        return result
