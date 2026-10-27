"""Single-host SQLite fixture registry and conservative cross-process leases.

No external calls here. Observations must come from the project's verified provider.
Expired leases never become available automatically: unknown effects require review.
"""
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

class FixtureError(ValueError):
    pass

def require(value, code):
    if not value: raise FixtureError(code)

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def safe(value):
    if isinstance(value, dict):
        for k,v in value.items():
            require(not re.search(r'(?i)^(password|passwd|pwd|token|cookie|authorization|secret|phone|mobile)$',k), 'SENSITIVE_FIELD_FORBIDDEN')
            safe(v)
    elif isinstance(value,list):
        for v in value: safe(v)
    elif isinstance(value,str):
        require(not re.search(r'(?i)\bBearer\s+\S+|-----BEGIN .*PRIVATE KEY|(?<![A-Za-z0-9])1[3-9]\d{9}(?![A-Za-z0-9])',value),'SENSITIVE_VALUE_FORBIDDEN')
    canonical(value)

def identifier(value):
    require(isinstance(value,str) and 0<len(value)<=200 and not any(c in value for c in '\n\r\x00'), 'IDENTIFIER_INVALID')
    return value

def database_path(root):
    root=Path(root).resolve()
    try:
        common=subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
        return (root/common).resolve()/'ai-test-fixtures'/'registry.sqlite3'
    except (OSError,subprocess.CalledProcessError):
        return root/'.ai-test'/'fixtures'/'registry.sqlite3'

class Registry:
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with self.tx() as db:
            schema='''
            CREATE TABLE IF NOT EXISTS meta(version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS targets(ref TEXT PRIMARY KEY,body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS blueprints(key TEXT,version TEXT,body TEXT NOT NULL,PRIMARY KEY(key,version));
            CREATE TABLE IF NOT EXISTS bindings(key TEXT,version TEXT,target TEXT,local_id TEXT,physical TEXT,
                state TEXT NOT NULL,observed TEXT,expires REAL,PRIMARY KEY(key,version,target));
            CREATE TABLE IF NOT EXISTS leases(id TEXT PRIMARY KEY,run TEXT,expires REAL,state TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS locks(lease TEXT,physical TEXT,mode TEXT,snapshot TEXT,PRIMARY KEY(lease,physical));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at REAL,action TEXT,body TEXT);
            CREATE TABLE IF NOT EXISTS intents(id TEXT PRIMARY KEY,plan_hash TEXT,step TEXT,state TEXT,body TEXT);
            '''
            for statement in schema.split(';'):
                if statement.strip():db.execute(statement)
            rows=db.execute('select version from meta').fetchall()
            if not rows: db.execute('insert into meta values(2)')
            else:
                require(len(rows)==1 and rows[0][0] in (1,2),'DATABASE_VERSION_UNSUPPORTED')
                if rows[0][0]==1:
                    require(not db.execute("select 1 from leases where state='active'").fetchone(),'SCHEMA_MIGRATION_ACTIVE_LEASES')
                    for row in db.execute('select key,version,target,physical from bindings').fetchall():
                        parts=json.loads(row['physical']);require(len(parts)==6,'PHYSICAL_KEY_INVALID')
                        db.execute('update bindings set physical=?,expires=0 where key=? and version=? and target=?',
                                   (canonical(parts[:3]+parts[4:]),row['key'],row['version'],row['target']))
                    db.execute('update meta set version=2')
        os.chmod(self.path,0o600)
    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA busy_timeout=10000');db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback();raise
        finally:db.close()
    def audit(self,db,action,body):
        safe(body);db.execute('insert into audit(at,action,body) values(?,?,?)',(time.time(),action,canonical(body)))
    def _target(self,db,ref):
        r=db.execute('select body from targets where ref=?',(ref,)).fetchone();require(r is not None,'TARGET_UNMAPPED');return json.loads(r[0])
    def target(self,ref):
        with self.tx() as db:return self._target(db,ref)
    def add_target(self,target):
        safe(target)
        require(set(target)=={'target_ref','stage','zone','organization','salon','role','platform','build'},'TARGET_FIELDS_INVALID')
        for v in target.values():identifier(v)
        with self.tx() as db:
            old=db.execute('select body from targets where ref=?',(target['target_ref'],)).fetchone()
            require(not old or old[0]==canonical(target),'TARGET_IMMUTABLE_NEW_REF_REQUIRED')
            db.execute('insert or ignore into targets values(?,?)',(target['target_ref'],canonical(target)))
    def add_blueprints(self,blueprints):
        require(isinstance(blueprints,list) and blueprints,'BLUEPRINTS_REQUIRED')
        with self.tx() as db:
            allbp={(r['key'],r['version']):json.loads(r['body']) for r in db.execute('select * from blueprints')}
            for b in blueprints:
                safe(b);require(set(b)=={'fixture_key','version','entity','pool','attributes','requires'},'BLUEPRINT_FIELDS_INVALID')
                for k in ('fixture_key','version','entity'):identifier(b[k])
                require(b['version'] not in {'latest','*'},'EXPLICIT_VERSION_REQUIRED')
                require(b['pool'] in {'base','scenario','run'} and isinstance(b['attributes'],dict) and isinstance(b['requires'],list),'BLUEPRINT_INVALID')
                key=(b['fixture_key'],b['version']);require(key not in allbp or allbp[key]==b,'BLUEPRINT_IMMUTABLE');allbp[key]=b
            done=set()
            def visit(k,active):
                require(k in allbp,'DEPENDENCY_MISSING');require(k not in active,'DEPENDENCY_CYCLE')
                if k in done:return
                for ref in allbp[k]['requires']:
                    require(isinstance(ref,dict) and set(ref)=={'fixture_key','version'},'DEPENDENCY_INVALID')
                    visit((ref['fixture_key'],ref['version']),active|{k})
                done.add(k)
            for k in allbp:visit(k,set())
            for b in blueprints:db.execute('insert or ignore into blueprints values(?,?,?)',(b['fixture_key'],b['version'],canonical(b)))
    def _blueprint(self,db,key,version):
        r=db.execute('select body from blueprints where key=? and version=?',(key,version)).fetchone()
        require(r is not None,'BLUEPRINT_UNMAPPED');return json.loads(r[0])
    def bind(self,key,version,target,local_id):
        local_id=identifier(str(local_id));safe(local_id)
        with self.tx() as db:
            t=self._target(db,target);b=self._blueprint(db,key,version)
            physical=canonical([t[k] for k in ('stage','zone','organization')]+[b['entity'],local_id])
            old=db.execute('select * from bindings where key=? and version=? and target=?',(key,version,target)).fetchone()
            require(not old or old['local_id']==local_id,'BINDING_IMMUTABLE_NEW_VERSION_REQUIRED')
            db.execute('insert or ignore into bindings values(?,?,?,?,?,?,?,?)',(key,version,target,local_id,physical,'unknown',None,0))
            self.audit(db,'bind',dict(fixture_key=key,version=version,target_ref=target))
    def _binding(self,db,key,version,target):
        r=db.execute('select * from bindings where key=? and version=? and target=?',(key,version,target)).fetchone()
        require(r is not None,'BINDING_MISSING');return dict(r)
    def _matches(self,db,b,observation,expected_state=True):
        require(isinstance(observation,dict) and set(observation)=={'local_id','target','attributes','evidence_ref','observed_at'},'OBSERVATION_FIELDS_INVALID')
        safe(observation);identifier(observation['evidence_ref'])
        at=observation['observed_at']
        require(type(at) in (int,float) and math.isfinite(at) and time.time()-60<=at<=time.time()+5,'OBSERVATION_STALE_OR_INVALID')
        require(str(observation['local_id'])==b['local_id'] and observation['target']==self._target(db,b['target']),'OBSERVATION_IDENTITY_MISMATCH')
        attrs=observation['attributes'];expected=self._blueprint(db,b['key'],b['version'])['attributes']
        require(isinstance(attrs,dict),'OBSERVATION_ATTRIBUTES_INVALID')
        if expected_state:require(all(k in attrs and attrs[k]==v for k,v in expected.items()),'OBSERVATION_STATE_MISMATCH')
    def observe(self,key,version,target,observation,ttl=300):
        require(type(ttl) is int and 0<ttl<=86400,'TTL_INVALID');error=None
        with self.tx() as db:
            b=self._binding(db,key,version,target)
            # Replaying a receipt must neither renew health nor poison fresh evidence.
            old=json.loads(b['observed']) if b['observed'] else {}
            require(isinstance(observation,dict) and type(observation.get('observed_at')) in (int,float),'OBSERVATION_TIME_REQUIRED')
            require(observation['observed_at']>old.get('observed_at',0),'OBSERVATION_NOT_NEW')
            try:self._matches(db,b,observation)
            except FixtureError as e:error=e
            if error:
                db.execute("update bindings set state='quarantined',expires=0 where physical=?",(b['physical'],))
            else:
                require(b['state'] not in {'consumed','quarantined'},'RECONCILIATION_REQUIRED')
                db.execute("update bindings set state='healthy',observed=?,expires=? where key=? and version=? and target=?",(canonical(observation),observation['observed_at']+ttl,key,version,target))
            self.audit(db,'observe',dict(fixture_key=key,target_ref=target,accepted=not bool(error)))
        if error:raise error
        return self.resolve(key,version,target)
    def _resolve(self,db,key,version,target,allow_expired=False):
        b=self._binding(db,key,version,target)
        require(b['state']=='healthy' and (allow_expired or b['expires']>time.time()),'FIXTURE_NOT_HEALTHY')
        # Aliases may not hide a poisoned physical object.
        poison=db.execute("select 1 from bindings where physical=? and state in ('quarantined','consumed')",(b['physical'],)).fetchone()
        require(not poison,'PHYSICAL_OBJECT_UNAVAILABLE')
        observed=b.pop('observed')
        return {**b,'observation':json.loads(observed) if observed else None}
    def resolve(self,key,version,target):
        with self.tx() as db:return self._resolve(db,key,version,target)
    def invalidate(self,key,version,target,reason,evidence_ref):
        """Quarantine known physical aliases on trusted, complete drift evidence.

        Does not release leases, remove bindings, adopt a new identity or restore
        health. Transport failures must not call this operation.
        """
        identifier(reason);identifier(evidence_ref)
        with self.tx() as db:
            b=self._binding(db,key,version,target)
            db.execute("update bindings set state='quarantined',expires=0 where physical=?",(b['physical'],))
            self.audit(db,'invalidate',dict(fixture_key=key,version=version,target_ref=target,reason=reason,evidence_ref=evidence_ref))

    def restore_consumed(self,key,version,target,lid,owner,observation,ttl=300):
        """Reconcile an exact restored run instance after its latest owned writer released.

        This never unlocks active/expired leases or clears quarantine/physical aliases.
        Provider evidence is trusted locally, as in observe(); it is not a remote attestation.
        """
        require(type(ttl) is int and 0<ttl<=86400,'TTL_INVALID')
        with self.tx() as db:
            b=self._binding(db,key,version,target)
            bp=self._blueprint(db,key,version)
            lease=db.execute('select * from leases where id=?',(lid,)).fetchone()
            require(lease and lease['run']==owner and lease['state']=='released','RESTORE_RELEASED_OWNER_REQUIRED')
            require(bp['pool']=='run' and b['state']=='consumed','RESTORE_CONSUMED_RUN_REQUIRED')
            aliases=db.execute('select * from bindings where physical=?',(b['physical'],)).fetchall()
            require(len(aliases)==1,'RESTORE_ALIASES_REQUIRE_RECONCILIATION')
            require(not db.execute("select 1 from locks join leases on leases.id=locks.lease where physical=? and leases.state='active'",(b['physical'],)).fetchone(),'RESTORE_ACTIVE_LEASE')
            lock=db.execute("select * from locks where lease=? and physical=? and mode='write'",(lid,b['physical'])).fetchone()
            require(lock is not None,'RESTORE_WRITE_SNAPSHOT_REQUIRED')
            frozen=json.loads(lock['snapshot'])
            require((frozen['key'],frozen['version'],frozen['target'],frozen['local_id'])==(key,version,target,b['local_id']),'RESTORE_BINDING_MISMATCH')
            latest=db.execute("select leases.id from locks join leases on leases.id=locks.lease where physical=? and mode='write' order by leases.created desc,leases.id desc limit 1",(b['physical'],)).fetchone()
            require(latest and latest['id']==lid,'RESTORE_LATEST_WRITER_REQUIRED')
            released_at=None
            for event in db.execute("select at,body from audit where action='lease_release' order by id desc"):
                if json.loads(event['body']).get('lease_id')==lid:
                    released_at=event['at'];break
            require(released_at is not None,'RESTORE_RELEASE_RECEIPT_REQUIRED')
            self._matches(db,b,observation)
            require(observation['observed_at']>released_at and observation['observed_at']>frozen['observation']['observed_at'],'RESTORE_FRESH_READBACK_REQUIRED')
            require(observation['attributes']==frozen['observation']['attributes'],'RESTORE_SNAPSHOT_MISMATCH')
            db.execute("update bindings set state='healthy',observed=?,expires=? where key=? and version=? and target=?",
              (canonical(observation),observation['observed_at']+ttl,key,version,target))
            self.audit(db,'restore_consumed',dict(fixture_key=key,version=version,target_ref=target,lease_id=lid,run_id=owner))
        return dict(status='healthy',fixture_key=key,version=version,target_ref=target,local_id=b['local_id'])

    def catalog(self):
        with self.tx() as db:
            return {'status':'ready','blueprints':[json.loads(r[0]) for r in db.execute('select body from blueprints order by key,version')],
                'targets':[json.loads(r[0]) for r in db.execute('select body from targets order by ref')],
                'bindings':[dict(r) for r in db.execute('select key,version,target,local_id,state,expires from bindings order by key,version,target')]}
    def acquire(self,requests,run_id,ttl=300,owner_claim=None):
        return self._acquire(requests,run_id,ttl,owner_claim)
    def acquire_health_check(self,requests,run_id,ttl=300,owner_claim=None):
        """Reserve a read-only snapshot before refreshing expired health.

        Binding state, physical poison and active/expired lease conflicts remain
        atomic with insertion. Ordinary consumers still require fresh health.
        """
        require(isinstance(requests,list) and requests and all(isinstance(r,dict) and r.get('mode')=='read' for r in requests),'HEALTH_CHECK_READ_ONLY')
        return self._acquire(requests,run_id,ttl,owner_claim,health_check=True)
    def _acquire(self,requests,run_id,ttl=300,owner_claim=None,health_check=False):
        identifier(run_id);require(type(ttl) is int and 0<ttl<=3600,'TTL_INVALID');require(isinstance(requests,list) and requests,'EFFECT_SET_REQUIRED')
        with self.tx() as db:
            if owner_claim is not None:
                from .coordination import _owned_rows
                _owned_rows(db,owner_claim,{'active'})
                require(owner_claim['owner_run']==run_id,'LEASE_EXECUTION_OWNER_MISMATCH')
            effects={}
            for req in requests:
                require(set(req)=={'fixture_key','version','target_ref','mode'} and req['mode'] in {'read','write'},'EFFECT_INVALID')
                b=self._resolve(db,req['fixture_key'],req['version'],req['target_ref'],allow_expired=health_check)
                bp=self._blueprint(db,b['key'],b['version'])
                require(req['mode']!='write' or bp['pool']=='run','SHARED_POOL_WRITE_FORBIDDEN')
                prev=effects.get(b['physical']);mode='write' if req['mode']=='write' or prev and prev['mode']=='write' else 'read'
                effects[b['physical']]={'mode':mode,'binding':b}
            for physical,item in effects.items():
                for row in db.execute("select locks.mode,leases.expires from locks join leases on leases.id=locks.lease where locks.physical=? and leases.state='active'",(physical,)):
                    require(row['expires']>time.time(),'EXPIRED_LEASE_RECONCILIATION_REQUIRED')
                    require(row['mode']=='read' and item['mode']=='read','LEASE_CONFLICT')
            lid=uuid.uuid4().hex;now=time.time();db.execute('insert into leases values(?,?,?,?,?)',(lid,run_id,now+ttl,'active',now))
            for physical,item in effects.items():db.execute('insert into locks values(?,?,?,?)',(lid,physical,item['mode'],canonical(item['binding'])))
            self.audit(db,'lease_acquire',dict(lease_id=lid,run_id=run_id,resources=len(effects),health_check=health_check))
            if owner_claim is not None:
                self.audit(db,'execution_dependency_lease',dict(lease_id=lid,claim=owner_claim,requests=requests))
            return {'status':'ready','lease_id':lid,'run_id':run_id,'expires':now+ttl,'physical_keys':sorted(effects)}
    def _lease(self,db,lid,owner):
        row=db.execute('select * from leases where id=?',(lid,)).fetchone()
        require(row is not None and row['run']==owner and row['state']=='active','LEASE_OWNER_OR_STATE_MISMATCH')
        require(row['expires']>time.time(),'LEASE_EXPIRED');return row
    def _lease_resources(self,db,lid):
        for lock in db.execute('select * from locks where lease=?',(lid,)):
            frozen=json.loads(lock['snapshot'])
            current=self._resolve(db,frozen['key'],frozen['version'],frozen['target'])
            require(current['physical']==frozen['physical'] and current['local_id']==frozen['local_id']
                    and current['observation']['attributes']==frozen['observation']['attributes'],'LEASE_RESOURCE_DRIFT')
    def assert_lease(self,lid,owner):
        with self.tx() as db:
            self._lease(db,lid,owner);self._lease_resources(db,lid)
    def heartbeat(self,lid,owner,ttl=300):
        require(type(ttl) is int and 0<ttl<=3600,'TTL_INVALID')
        with self.tx() as db:
            self._lease(db,lid,owner);self._lease_resources(db,lid);db.execute('update leases set expires=? where id=?',(time.time()+ttl,lid))
    def release(self,lid,owner,observations):
        with self.tx() as db:
            self._lease(db,lid,owner);locks=list(db.execute('select * from locks where lease=?',(lid,)))
            outcomes=[]
            for lock in locks:
                b=json.loads(lock['snapshot']);obs=observations.get(lock['physical'],observations.get(b['local_id']))
                require(obs is not None,'RELEASE_READBACK_REQUIRED');self._matches(db,b,obs,expected_state=False)
                require(obs['observed_at']>b['observation']['observed_at'],'RELEASE_FRESH_READBACK_REQUIRED')
                # Base readers must see unchanged state. A writer's instance is consumed until separately reconciled.
                unchanged=obs['attributes']==b['observation']['attributes']
                poison=db.execute("select 1 from bindings where physical=? and state in ('quarantined','consumed')",(lock['physical'],)).fetchone()
                outcomes.append((lock['physical'],'quarantined' if poison or not unchanged and lock['mode']=='read' else 'consumed' if lock['mode']=='write' else 'healthy'))
            for physical,state in outcomes:
                if state!='healthy':db.execute('update bindings set state=?,expires=0 where physical=?',(state,physical))
            db.execute("update leases set state='released' where id=?",(lid,));self.audit(db,'lease_release',dict(lease_id=lid,outcomes=outcomes))
            return {'status':'released','outcomes':outcomes}
