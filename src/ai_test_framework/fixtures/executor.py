"""Offline dependency preparation and durable provider-backed ensure operations.

Providers are trusted Python objects supplied by application code, never loaded
from blueprint strings. Creates remain in existing business factory adapters.
"""
import json
import time
import uuid
from .registry import FixtureError, canonical, digest, identifier, require, safe


def prepare(registry, needs, target_ref, capabilities, provider_contract=None):
    require(isinstance(needs,list) and needs,'DATA_NEEDS_REQUIRED');safe(needs)
    target=registry.target(target_ref);steps=[];visited=set()
    with registry.tx() as db:
        def visit(key,version):
            if (key,version) in visited:return
            bp=registry._blueprint(db,key,version)
            for d in bp['requires']:visit(d['fixture_key'],d['version'])
            visited.add((key,version))
            steps.append({'blueprint':bp,'operation':'ensure','status':'ready' if bp['entity'] in capabilities else 'blocked',
                          'reason':None if bp['entity'] in capabilities else 'provider_capability_missing'})
        for n in needs:
            require(set(n)=={'requirement_id','case_id','fixture_key','version','usage'},'DATA_NEED_FIELDS_INVALID')
            for k in ('requirement_id','case_id','fixture_key','version'):identifier(n[k])
            require(n['usage'] in {'read','write'},'USAGE_INVALID')
            bp=registry._blueprint(db,n['fixture_key'],n['version'])
            require(n['usage']!='write' or bp['pool']=='run','SHARED_POOL_WRITE_FORBIDDEN')
            visit(n['fixture_key'],n['version'])
    plan={'schema_version':1,'target':target,'needs':needs,'steps':steps,
          'status':'blocked' if any(s['status']=='blocked' for s in steps) else 'ready'}
    if provider_contract is not None:safe(provider_contract);plan['provider_contract']=provider_contract
    return {**plan,'sha256':digest(plan)}


def apply(registry, plan, provider, authorization_hash):
    safe(plan);body={k:v for k,v in plan.items() if k!='sha256'}
    require(digest(body)==plan.get('sha256')==authorization_hash,'PLAN_OR_AUTHORIZATION_HASH_MISMATCH')
    require(plan['status']=='ready','PLAN_BLOCKED')
    target=registry.target(plan['target']['target_ref']);require(target==plan['target'],'TARGET_CHANGED')
    expected=prepare(registry,plan['needs'],target['target_ref'],provider.capabilities(target),provider.contract() if hasattr(provider,'contract') else None)
    require(expected==plan,'PLAN_OR_CAPABILITY_CHANGED')
    # Serialize factory preparation for the physical tenant, regardless of role/profile alias.
    scope='factory:'+digest([target[k] for k in ('stage','zone','organization')])
    owner=uuid.uuid4().hex
    with registry.tx() as db:
        old=db.execute('select * from intents where id=?',(scope,)).fetchone()
        if old and old['state']!='released':return {'status':'blocked','code':'FACTORY_SCOPE_RECONCILIATION_REQUIRED','steps':[]}
        db.execute('insert or replace into intents values(?,?,?,?,?)',(scope,plan['sha256'],'scope','executing',canonical({'owner':owner})))
    results=[];unknown=False
    try:
        for step in plan['steps']:
            bp=step['blueprint'];key=bp['fixture_key'];version=bp['version'];ref=target['target_ref']
            iid='ensure:'+digest([scope,target['salon'],key,version])
            with registry.tx() as db:
                previous=db.execute('select * from intents where id=?',(iid,)).fetchone()
                if previous and previous['state']=='unknown':
                    unknown=True;raise FixtureError('UNKNOWN_WRITE_RECONCILIATION_REQUIRED')
            matches=provider.find(bp,target)
            require(isinstance(matches,list) and len(matches)<=1,'FIXTURE_MULTIPLE_MATCHES')
            if previous and previous['state']=='verified':require(len(matches)==1,'PREVIOUS_FIXTURE_DISAPPEARED')
            if not matches:
                with registry.tx() as db:
                    bound=db.execute('select 1 from bindings where key=? and version=? and target=?',(key,version,ref)).fetchone()
                    require(not bound,'BOUND_FIXTURE_MISSING_RECONCILE_BEFORE_CREATE')
                # Commit intent before the only operation allowed to produce external effects.
                with registry.tx() as db:
                    db.execute('insert or replace into intents values(?,?,?,?,?)',(iid,plan['sha256'],key,'unknown',canonical({'fixture_key':key,'version':version,'target_ref':ref})))
                unknown=True
                obj=provider.create(bp,target)
            else:obj=matches[0]
            observation=provider.detail(obj,bp,target)
            require(isinstance(observation,dict),'READBACK_REQUIRED');safe(observation)
            require(observation['target']==target,'OBSERVATION_IDENTITY_MISMATCH')
            registry.bind(key,version,ref,str(observation['local_id']))
            registry.observe(key,version,ref,observation)
            with registry.tx() as db:
                db.execute('insert or replace into intents values(?,?,?,?,?)',(iid,plan['sha256'],key,'verified',canonical({'fixture_key':key,'version':version,'target_ref':ref})))
            unknown=False
            results.append({'fixture_key':key,'version':version,'target_ref':ref,'status':'verified','action':'reused' if matches else 'created'})
        return {'status':'ready','plan_sha256':plan['sha256'],'steps':results}
    except Exception as e:
        # External exception text may contain credentials/request bodies. Never export it.
        return {'status':'blocked','code':str(e) if isinstance(e,FixtureError) else 'PROVIDER_FAILED_RECONCILE_BEFORE_RETRY',
                'plan_sha256':plan['sha256'],'steps':results}
    finally:
        with registry.tx() as db:
            db.execute('update intents set state=? where id=?',('unknown' if unknown else 'released',scope))
            registry.audit(db,'prepare_finished',{'plan_sha256':plan['sha256'],'unknown':unknown,'completed_steps':len(results)})


def reconcile(registry,plan,provider):
    """Read-only reconciliation of a settled unknown write, never an active worker."""
    safe(plan);target=registry.target(plan['target']['target_ref'])
    expected=prepare(registry,plan['needs'],target['target_ref'],provider.capabilities(target),
                     provider.contract() if hasattr(provider,'contract') else None)
    require(plan==expected,'RECONCILIATION_PLAN_CHANGED')
    scope='factory:'+digest([target[k] for k in ('stage','zone','organization')])
    with registry.tx() as db:
        row=db.execute('select * from intents where id=?',(scope,)).fetchone()
        require(row is not None and row['state']=='unknown' and row['plan_hash']==plan['sha256'],'RECONCILIATION_SCOPE_NOT_SETTLED_UNKNOWN')
        db.execute("update intents set state='reconciling' where id=?",(scope,))
    resolved=[];done=False
    try:
        for step in plan['steps']:
            bp=step['blueprint'];iid='ensure:'+digest([scope,target['salon'],bp['fixture_key'],bp['version']])
            with registry.tx() as db:row=db.execute('select * from intents where id=?',(iid,)).fetchone()
            if not row or row['state']!='unknown':continue
            require(row['plan_hash']==plan['sha256'],'RECONCILIATION_INTENT_PLAN_MISMATCH')
            matches=provider.find(bp,target)
            require(isinstance(matches,list) and len(matches)==1,'UNKNOWN_WRITE_NOT_UNIQUELY_OBSERVED')
            observation=provider.detail(matches[0],bp,target)
            registry.bind(bp['fixture_key'],bp['version'],target['target_ref'],observation['local_id'])
            registry.observe(bp['fixture_key'],bp['version'],target['target_ref'],observation)
            with registry.tx() as db:db.execute("update intents set state='verified' where id=?",(iid,))
            resolved.append(bp['fixture_key'])
        with registry.tx() as db:
            # Execution ownership is reconciled by its canonical provider proof,
            # separately from these business inputs; never clear that claim here.
            from .coordination import STEP as execution_owner_step
            pending=db.execute("select 1 from intents where plan_hash=? and state='unknown' and not (step=? and id like 'execution-claim:%')",(plan['sha256'],execution_owner_step)).fetchone()
            require(not pending,'UNKNOWN_INTENTS_REMAIN')
        done=True
        return {'status':'reconciled','resolved':resolved,'business_writes':0}
    finally:
        with registry.tx() as db:
            db.execute('update intents set state=? where id=?',('released' if done else 'unknown',scope))


def authorize_absent_retry(registry, plan, provider, proof, authorization_hash):
    """Explicitly settle a stopped, proven absent write before a new authorized run.

    Unlike reconcile(), this cannot adopt an object or clear a binding. The
    trusted business adapter must prove async settlement and unchanged context;
    the kernel repeats the absence lookup and refuses outstanding tenant leases.
    No business create is performed here. Old evidence remains in the audit.
    """
    import math
    safe(proof)
    require(plan == prepare(registry, plan['needs'], plan['target']['target_ref'],
                           provider.capabilities(plan['target']),
                           provider.contract() if hasattr(provider, 'contract') else None), 'RECONCILIATION_PLAN_CHANGED')
    require(authorization_hash == plan['sha256'] == proof.get('plan_sha256'), 'RETRY_AUTHORIZATION_MISMATCH')
    at = proof.get('observed_at')
    require(type(at) in (int, float) and math.isfinite(at) and time.time()-60 <= at <= time.time()+5,
            'RETRY_PROOF_STALE')
    require(proof.get('settled') is True, 'RETRY_ASYNC_NOT_SETTLED')
    identifier(proof.get('evidence_ref'))
    target = plan['target']; tenant = [target[k] for k in ('stage','zone','organization')]
    scope = 'factory:' + digest(tenant)
    with registry.tx() as db:
        original = db.execute('select * from intents where id=?', (scope,)).fetchone()
        require(original and original['state']=='unknown' and original['plan_hash']==plan['sha256'], 'RETRY_SCOPE_MISMATCH')
        original = dict(original)
        require(proof.get('previous_scope_sha256')==digest(original), 'RETRY_PROOF_ATTEMPT_MISMATCH')
        pending = [dict(row) for row in db.execute("select * from intents where plan_hash=? and state='unknown' and step!='scope'", (plan['sha256'],))]
    expected = {}
    for step in plan['steps']:
        bp = step['blueprint']; iid = 'ensure:' + digest([scope,target['salon'],bp['fixture_key'],bp['version']])
        if any(row['id']==iid for row in pending): expected[iid]=bp
    require(expected and set(expected)=={row['id'] for row in pending}, 'RETRY_UNKNOWN_SET_MISMATCH')
    require(sorted(proof.get('absent_keys',[]))==sorted(bp['fixture_key'] for bp in expected.values()), 'RETRY_ABSENT_SET_MISMATCH')
    for bp in expected.values():
        matches = provider.find(bp,target)
        require(isinstance(matches,list) and not matches, 'RETRY_OBJECT_OBSERVED')
    with registry.tx() as db:
        current = db.execute('select * from intents where id=?',(scope,)).fetchone()
        require(current and dict(current)==original,'RETRY_SCOPE_CHANGED')
        for lock in db.execute("select physical from locks join leases on leases.id=locks.lease where leases.state='active'"):
            require(json.loads(lock['physical'])[:3]!=tenant,'RETRY_TENANT_LEASE_UNRESOLVED')
        for row in pending:
            current=db.execute('select * from intents where id=?',(row['id'],)).fetchone()
            require(current and dict(current)==row,'RETRY_INTENT_CHANGED')
            bp=expected[row['id']]
            require(not db.execute('select 1 from bindings where key=? and version=? and target=?',
                                   (bp['fixture_key'],bp['version'],target['target_ref'])).fetchone(),'RETRY_BOUND_OBJECT_MISSING')
        for row in pending:db.execute("update intents set state='reconciled_absent' where id=?",(row['id'],))
        db.execute("update intents set state='released' where id=?",(scope,))
        registry.audit(db,'explicit_absent_retry_authorized',dict(previous_scope=original,previous_intents=pending,proof=proof))
    return dict(status='reconciled_absent',business_writes=0,absent_keys=proof['absent_keys'])
