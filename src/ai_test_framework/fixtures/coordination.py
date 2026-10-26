"""Local execution ownership, separate from native fixture health.

Uses the existing registry transaction and intent table. There is deliberately no
automatic expiry: a crashed writer needs fresh provider evidence and a dead PID.
These claims coordinate participating executors; they do not grant permissions or
lock external users out of the product.
"""
import json
import math
import os
import re
import time
import uuid

from .registry import canonical, digest, identifier, require, safe

STEP = 'execution-owner-claim'


def _ids(resources):
    require(isinstance(resources, list) and 0 < len(resources) <= 128, 'EXECUTION_RESOURCES_INVALID')
    require(all(isinstance(value, str) for value in resources), 'EXECUTION_RESOURCES_INVALID')
    for resource in resources:
        identifier(resource)
    require(len(resources) == len(set(resources)), 'EXECUTION_RESOURCES_DUPLICATED')
    safe(resources)
    return ['execution-claim:' + digest(value) for value in sorted(resources)]


def _writer_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire(registry, owner_run, resources, context_sha256):
    identifier(owner_run)
    safe(owner_run)
    require(isinstance(context_sha256, str) and re.fullmatch('[0-9a-f]{64}', context_sha256), 'EXECUTION_CONTEXT_HASH_INVALID')
    ids = _ids(resources)
    claim = dict(schema_version=1, owner_run=owner_run, holder_id=uuid.uuid4().hex,
                 owner_pid=os.getpid(), resources=sorted(resources), resource_ids=ids,
                 context_sha256=context_sha256, acquired_at=time.time())
    with registry.tx() as db:
        for ident in ids:
            row = db.execute('select * from intents where id=?', (ident,)).fetchone()
            require(not row or row['step'] == STEP, 'EXECUTION_RESOURCE_NAMESPACE_CONFLICT')
            require(not row or row['state'] == 'released', 'EXECUTION_RESOURCE_BUSY')
        for ident in ids:
            db.execute('insert or replace into intents values(?,?,?,?,?)',
                       (ident, context_sha256, STEP, 'active', canonical(claim)))
        registry.audit(db, 'execution_claim_acquire', claim)
    return claim


def _owned_rows(db, claim, states):
    require(isinstance(claim, dict), 'EXECUTION_CLAIM_INVALID')
    safe(claim)
    ids = _ids(claim.get('resources'))
    require(claim.get('schema_version') == 1 and claim.get('resource_ids') == ids, 'EXECUTION_CLAIM_SET_MISMATCH')
    require(type(claim.get('owner_pid')) is int and claim['owner_pid'] > 0, 'EXECUTION_OWNER_PID_INVALID')
    for ident in ids:
        row = db.execute('select * from intents where id=?', (ident,)).fetchone()
        require(row and row['step'] == STEP and row['plan_hash'] == claim.get('context_sha256')
                and json.loads(row['body']) == claim, 'EXECUTION_CLAIM_OWNERSHIP_MISMATCH')
        require(row['state'] in states, 'EXECUTION_CLAIM_STATE_INVALID')
    return ids


def release(registry, claim, disposition, evidence_ref):
    require(disposition in {'released', 'unknown'}, 'EXECUTION_CLAIM_DISPOSITION_INVALID')
    identifier(evidence_ref)
    safe(evidence_ref)
    with registry.tx() as db:
        ids = _owned_rows(db, claim, {'active'})
        for ident in ids:
            db.execute('update intents set state=? where id=?', (disposition, ident))
        registry.audit(db, 'execution_claim_release', dict(owner_run=claim['owner_run'],
                       holder_id=claim['holder_id'], disposition=disposition, evidence_ref=evidence_ref))
    return dict(status=disposition, owner_run=claim['owner_run'], holder_id=claim['holder_id'])


def recover(registry, claim, proof):
    """Provider must prove the exact stopped workflow is safe before calling this.

    The kernel additionally checks full claim ownership, freshness and process
    liveness. A boolean 'force' flag or a timeout cannot free a claim.
    """
    require(isinstance(proof, dict), 'EXECUTION_RECOVERY_PROOF_INVALID')
    safe(proof)
    require(all(proof.get(key) == claim.get(key) for key in
                ['owner_run', 'holder_id', 'context_sha256']), 'EXECUTION_RECOVERY_SCOPE_MISMATCH')
    require(proof.get('resources_sha256') == digest(claim.get('resources')), 'EXECUTION_RECOVERY_SET_MISMATCH')
    observed = proof.get('observed_at')
    require(type(observed) in (int, float) and math.isfinite(observed)
            and time.time() - 60 <= observed <= time.time() + 5
            and observed > claim['acquired_at'], 'EXECUTION_RECOVERY_PROOF_STALE')
    identifier(proof.get('evidence_ref'))
    with registry.tx() as db:
        ids = _owned_rows(db, claim, {'active', 'unknown'})
        require(not _writer_alive(claim['owner_pid']), 'EXECUTION_WRITER_ALIVE')
        for ident in ids:
            db.execute("update intents set state='released' where id=?", (ident,))
        registry.audit(db, 'execution_claim_recover', dict(owner_run=claim['owner_run'],
                       holder_id=claim['holder_id'], proof=proof))
    return dict(status='released', owner_run=claim['owner_run'], holder_id=claim['holder_id'])
