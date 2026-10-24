"""Local, content-free estimates of Nowledge context volume in Codex JSONL.

Official turn totals belong to the entire Codex turn. Byte-based estimates here
are deliberately separate and are never a billing or quota measurement.
"""

import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path


_USAGE_KEYS = (
    'input_tokens', 'cached_input_tokens', 'output_tokens',
    'reasoning_output_tokens', 'total_tokens',
)
_ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}\Z')
_TOOL = re.compile(r'(?:mcp__nowledge_mem__|mcp__nowledge-mem__)([a-z][a-z0-9_]{0,63})\Z')
_INVOCATION = re.compile(r'\btools\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(')


def _identifier(value, fallback='unknown'):
    if not isinstance(value, str) or not value:
        return fallback
    if _ID.fullmatch(value):
        return value
    return 'sha256-' + hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]


def _timestamp(value):
    if isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return value
        except ValueError:
            pass
    return None


def _number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _usage(value):
    if not isinstance(value, dict):
        return None
    result = {key: value[key] for key in _USAGE_KEYS
              if isinstance(value.get(key), int) and not isinstance(value[key], bool)
              and value[key] >= 0}
    return result or None


def _size(value):
    if value is None:
        return 0
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return len(value.encode('utf-8'))


def _estimate(byte_count):
    return math.ceil(byte_count / 4)


def _javascript_code(source):
    """Mask strings and comments before identifying actual tool invocations.

    This bounded lexical recognizer does not execute JS. Dynamic property calls
    and template interpolation are deliberately unsupported; a name inside a
    shell argument, comment or sample string is not evidence of a tool call.
    """
    output = list(source)
    index = 0
    while index < len(source):
        start = index
        if source.startswith('//', index):
            end = source.find('\n', index)
            index = len(source) if end < 0 else end
        elif source.startswith('/*', index):
            end = source.find('*/', index + 2)
            index = len(source) if end < 0 else end + 2
        elif source[index] in "'\"`":
            quote = source[index]
            index += 1
            while index < len(source):
                if source[index] == '\\':
                    index += 2
                elif source[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
        else:
            index += 1
            continue
        output[start:index] = ' ' * (index - start)
    return ''.join(output)


def _tools(payload):
    name = payload.get('name', '')
    direct = _TOOL.fullmatch(name) if isinstance(name, str) else None
    if direct:
        return [direct.group(1)], False
    if name not in ('exec', 'functions.exec'):
        return [], False
    source = payload.get('input', payload.get('arguments', ''))
    if not isinstance(source, str):
        return [], False
    invocations = _INVOCATION.findall(_javascript_code(source))
    matches = [_TOOL.fullmatch(name) for name in invocations]
    nowledge = sorted({match.group(1) for match in matches if match})
    return nowledge, bool(nowledge and any(match is None for match in matches))


def _read_rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError('Invalid JSONL at line %d' % line_number) from None
            if not isinstance(row, dict):
                raise ValueError('Expected JSON object at line %d' % line_number)
            yield row


def analyze_codex_session(path, *, latest_turn=False):
    """Analyze a local session; optionally return its latest *matching* turn.

    No queries, tool responses, raw paths, or shell source survive into the
    result. Missing explicit turn_token_usage is reported as None, not zero.
    """
    session_id = None
    turns = []
    by_id = {}
    current = None
    pending = {}

    def get_turn(turn_id=None, timestamp=None):
        nonlocal current
        if turn_id is not None:
            identity = _identifier(turn_id)
        elif current is not None:
            return current
        else:
            identity = 'unattributed-1'
        if identity not in by_id:
            by_id[identity] = {
                'turn_id': identity, 'started_at': _timestamp(timestamp),
                'official_turn_usage': None, 'calls': [], '_responses': 0,
            }
            turns.append(by_id[identity])
        current = by_id[identity]
        return current

    for row in _read_rows(path):
        payload = row.get('payload')
        if not isinstance(payload, dict):
            continue
        kind = row.get('type')
        subtype = payload.get('type')
        if kind == 'session_meta':
            session_id = _identifier(payload.get('id'), 'unknown')
        elif kind == 'event_msg' and subtype == 'task_started':
            get_turn(payload.get('turn_id'), row.get('timestamp'))
        elif kind == 'turn_context':
            get_turn(payload.get('turn_id'), row.get('timestamp'))
        elif kind == 'token_usage_record':
            turn = get_turn(payload.get('turn_id'))
            turn['_responses'] += 1
            usage = _usage(payload.get('turn_token_usage'))
            if usage is not None:
                turn['official_turn_usage'] = usage
        elif kind == 'response_item' and subtype in ('function_call', 'custom_tool_call'):
            names, mixed = _tools(payload)
            if not names:
                continue
            turn = get_turn()
            request_bytes = _size(payload.get('name')) + _size(payload.get('input', payload.get('arguments')))
            call = {
                'tools': names, 'mixed_exec': mixed,
                'precision': 'upper_bound' if mixed else 'estimate',
                'request_bytes': request_bytes, 'response_bytes': 0,
                'estimated_request_tokens': _estimate(request_bytes),
                'estimated_response_tokens': 0, 'context_replay_count': 0,
                '_response_index': None,
            }
            turn['calls'].append(call)
            call_id = payload.get('call_id')
            if isinstance(call_id, str):
                pending[call_id] = (turn, call)
        elif kind == 'response_item' and subtype in ('function_call_output', 'custom_tool_call_output'):
            matched = pending.get(payload.get('call_id'))
            if matched is not None:
                turn, call = matched
                call['response_bytes'] += _size(payload.get('output'))
                if call['_response_index'] is None:
                    call['_response_index'] = turn['_responses']

    selected = []
    for turn in turns:
        responses = turn.pop('_responses')
        if not turn['calls']:
            continue
        for call in turn['calls']:
            response_index = call.pop('_response_index')
            call['context_replay_count'] = 0 if response_index is None else responses - response_index
            call['estimated_response_tokens'] = _estimate(call['response_bytes'])
            request = call['estimated_request_tokens']
            response = call['estimated_response_tokens']
            call['estimated_nowledge_token_volume'] = request + (request + response) * call['context_replay_count']
        turn['nowledge_call_count'] = len(turn['calls'])
        turn['tools'] = sorted({name for call in turn['calls'] for name in call['tools']})
        turn['precision'] = 'upper_bound' if any(c['mixed_exec'] for c in turn['calls']) else 'estimate'
        turn['estimated_nowledge_token_volume'] = sum(c['estimated_nowledge_token_volume'] for c in turn['calls'])
        selected.append(turn)
    if latest_turn:
        selected = selected[-1:]
    totals = [t['official_turn_usage'].get('total_tokens') if t['official_turn_usage'] else None for t in selected]
    summary = {
        'turn_count': len(selected),
        'nowledge_call_count': sum(t['nowledge_call_count'] for t in selected),
        'estimated_nowledge_token_volume': sum(t['estimated_nowledge_token_volume'] for t in selected),
        'official_turn_total_tokens': sum(totals) if totals and all(v is not None for v in totals) else None,
    }
    return {
        'session_id': session_id or 'sha256-' + hashlib.sha256(str(Path(path).resolve()).encode('utf-8')).hexdigest()[:24],
        'summary': summary, 'turns': selected,
        'methodology': {
            'classification': 'upper_bound' if any(t['precision'] == 'upper_bound' for t in selected) else 'estimate',
            'token_estimator': 'ceil(utf8_bytes / 4)',
            'volume_formula': 'request + (request + response) * context_replay_count',
            'replay_basis': 'token_usage_record events after tool output within the same turn',
            'official_usage_scope': 'whole Codex turn; not Nowledge attribution or quota',
            'unsupported_calls': 'dynamic JS, template interpolation, shell CLI invocations',
        },
    }


def compact_usage_summary(report):
    """Return numeric summary fields, without per-call detail or content."""
    summary = report.get('summary', {})
    return {
        'session_id': _identifier(report.get('session_id')),
        'turn_count': _number(summary.get('turn_count')),
        'nowledge_call_count': _number(summary.get('nowledge_call_count')),
        'estimated_nowledge_token_volume': _number(summary.get('estimated_nowledge_token_volume')),
        'official_turn_total_tokens': summary.get('official_turn_total_tokens')
        if isinstance(summary.get('official_turn_total_tokens'), int) else None,
        'precision': 'upper_bound' if report.get('methodology', {}).get('classification') == 'upper_bound' else 'estimate',
    }


def _ledger_entry(session_id, turn):
    # Explicit projection: even caller-supplied reports cannot persist bodies.
    return {
        'session_id': _identifier(session_id),
        'turn_id': _identifier(turn.get('turn_id')),
        'started_at': _timestamp(turn.get('started_at')),
        'nowledge_call_count': _number(turn.get('nowledge_call_count')),
        'estimated_nowledge_token_volume': _number(turn.get('estimated_nowledge_token_volume')),
        'official_turn_usage': _usage(turn.get('official_turn_usage')),
        'tools': sorted({name for name in turn.get('tools', []) if isinstance(name, str)
                         and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name)}),
        'precision': 'upper_bound' if turn.get('precision') == 'upper_bound' else 'estimate',
    }


def update_usage_ledger(path, report):
    """Atomically upsert content-free records keyed by session_id + turn_id.

    Advisory locking serializes local writers on macOS/Linux. Reanalyzing an
    active turn replaces its record; unchanged turns produce no file rewrite.
    """
    import fcntl

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = {}
        if path.exists():
            for row in _read_rows(path):
                entry = _ledger_entry(row.get('session_id'), row)
                rows[(entry['session_id'], entry['turn_id'])] = entry
        appended = updated = 0
        for turn in report.get('turns', []):
            entry = _ledger_entry(report.get('session_id'), turn)
            key = entry['session_id'], entry['turn_id']
            if key not in rows:
                appended += 1
            elif rows[key] != entry:
                updated += 1
            rows[key] = entry
        if appended or updated:
            fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    for entry in rows.values():
                        stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    return {'appended': appended, 'updated': updated, 'total': len(rows)}
