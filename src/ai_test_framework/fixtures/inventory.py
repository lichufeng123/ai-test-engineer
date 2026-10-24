"""Read-only source inventory. Never copy source literals or credential values."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SKIP = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'runs', 'outputs',
        'evidence', 'test-results', '.auth', '.tmp', 'source-materials', 'reference-docs'}
SUFFIXES = {'.py', '.ts', '.js', '.mjs', '.json', '.sh'}
ENTITY = re.compile(r'\b(member|customer|employee|staff|service|course|salon|brand|role|appointment|goal|order|question|scenario|fixture)[_-]?(?:id|ids|ref|key)\b', re.I)
CASE = re.compile(r'\b(?:CASE|TC|AISS|SBA|MVC)-[A-Z0-9][A-Z0-9_-]*\b')


def inventory(root, registry_root=None):
    root = Path(root).resolve()
    registry_root = Path(registry_root or root).resolve()
    candidates = []
    exclusions = set()
    for base in ('features', 'shared', 'bin', 'scripts', 'executors'):
        for p in (root / base).rglob('*'):
            rel = p.relative_to(root)
            if p.is_symlink() or any(x in SKIP for x in rel.parts):
                exclusions.add(str(rel)); continue
            if not p.is_file() or p.suffix not in SUFFIXES or '.local.' in p.name or p.name=='migration-inventory.json':
                continue
            if p.stat().st_size > 2_000_000:
                exclusions.add(str(rel)); continue
            candidates.append(p)
    registries = list(root.glob('features/**/execution_asset_register.json'))
    registries += list(registry_root.glob('.ai-test/work-items/*/artifacts.json'))
    registered, errors = {}, []

    def refs(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in {'path', 'script_ref', 'runner', 'script_path'} and isinstance(v, str):
                    yield v
                else:
                    yield from refs(v)
        elif isinstance(node, list):
            for v in node: yield from refs(v)

    for reg in registries:
        try:
            for ref in refs(json.loads(reg.read_text())):
                if Path(ref).is_absolute() or '..' in Path(ref).parts:
                    continue
                if Path(ref).suffix not in {'.py', '.ts', '.js', '.mjs', '.sh'}:
                    continue
                if any(x in SKIP for x in Path(ref).parts): continue
                p = root / ref
                if not p.exists() and reg.is_relative_to(root) and (reg.parent / ref).exists():
                    p = reg.parent / ref
                registered.setdefault(str(p.relative_to(root)), []).append(reg.name)
        except (OSError, ValueError):
            errors.append({'source': reg.name, 'status': 'unreadable_registry'})
    rows = []
    for p in candidates:
        rel = p.relative_to(root).as_posix()
        try: text = p.read_text()
        except (OSError, UnicodeError):
            errors.append({'source': rel, 'status': 'unreadable_source'}); continue
        hits = [{'line': n, 'field': m.group(0), 'entity': m.group(1).lower()}
                for n, line in enumerate(text.splitlines(), 1) for m in ENTITY.finditer(line)]
        executable = p.suffix in {'.py', '.ts', '.js', '.mjs', '.sh'}
        if not hits and not executable and rel not in registered: continue
        unit = bool(re.search(r'(?:test_|\.test\.|/tests/test_)', rel))
        rows.append({'feature_id': p.relative_to(root).parts[1] if rel.startswith('features/') else 'shared',
                     'script_ref': rel, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                     'registration': 'registered_present' if rel in registered else 'unregistered_present',
                     'old_fixture_ref': hits, 'entity': sorted({h['entity'] for h in hits}),
                     'case_ids': sorted(set(CASE.findall(text))), 'target_ref': None,
                     'operation': 'pending_analysis', 'state_dependencies': [],
                     'proposed_fixture_key': None, 'disposition': 'retain' if unit or not hits else 'defer',
                     'reason': 'offline unit/support asset; preserve' if unit or not hits else 'requires semantic binding review before mutation',
                     'blocker': None if unit or not hits else 'fixture_contract_review_pending',
                     'verification_ref': None})
    present = {r['script_ref'] for r in rows}
    for ref in registered.keys() - present:
        rows.append({'script_ref': ref, 'feature_id': 'pending',
                     'registration': 'registered_missing' if not (root / ref).exists() else 'registered_excluded',
                     'disposition': 'defer', 'reason': 'resolve registry reference before migration',
                     'blocker': 'source_not_in_inventory', 'verification_ref': None})
    workitems = []
    for path in registry_root.glob('.ai-test/work-items/*/manifest.json'):
        try:
            obj = json.loads(path.read_text())
            workitems.append({k: obj.get(k) for k in ('requirement_id', 'feature', 'environments', 'platforms')})
        except (ValueError, OSError): errors.append({'source': path.parent.name, 'status': 'unreadable_manifest'})
    return {'schema_version': 1, 'status': 'partial' if errors else 'inventoried',
            'source_root': str(root), 'registry_root': str(registry_root),
            'scope': ['features', 'shared', 'bin', 'scripts', 'executors', 'work-item asset references'],
            'exclusion_policy': sorted(SKIP) + ['symlinks', '*.local.*', 'files over 2 MB'],
            'excluded_count': len(exclusions), 'errors': errors, 'work_items': workitems,
            'summary': dict(Counter(r['registration'] for r in rows)),
            'consumers': sorted(rows, key=lambda r: r['script_ref']),
            'business_verification': 'not_performed', 'frequency_evidence': 'unknown'}
