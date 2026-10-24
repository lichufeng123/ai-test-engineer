"""Incremental run requirements and per-case fixture readiness, without business writes."""
import json
from .registry import FixtureError, canonical, digest, identifier, require, safe


def validate(need):
    safe(need)
    require(isinstance(need,dict) and set(need)=={'requirement_id','case_id','fixture_key','version','usage'},'DATA_NEED_FIELDS_INVALID')
    for k in ('requirement_id','case_id','fixture_key','version'):identifier(need[k])
    require(need['version'] not in {'latest','*'} and need['usage'] in {'read','write'},'DATA_NEED_INVALID')


def record(registry,run_id,need):
    identifier(run_id);validate(need)
    iid='needs:'+run_id
    with registry.tx() as db:
        row=db.execute('select * from intents where id=?',(iid,)).fetchone()
        body=json.loads(row['body']) if row else {'schema_version':1,'run_id':run_id,'needs':[]}
        require(not row or row['state']=='recording','DATA_NEEDS_FROZEN')
        slot=lambda n:(n['requirement_id'],n['case_id'],n['fixture_key'])
        old=[n for n in body['needs'] if slot(n)==slot(need)]
        require(not old or old==[need],'CASE_BINDING_CONFLICT')
        if not old:body['needs'].append(need)
        body['needs'].sort(key=lambda n:slot(n))
        db.execute('insert or replace into intents values(?,?,?,?,?)',(iid,digest(body),'data-needs','recording',canonical(body)))
    return {'status':'recorded','run_id':run_id,'count':len(body['needs'])}


def freeze(registry,run_id):
    identifier(run_id)
    with registry.tx() as db:
        row=db.execute('select * from intents where id=?',('needs:'+run_id,)).fetchone()
        require(row is not None,'DATA_NEEDS_MISSING');body=json.loads(row['body'])
        db.execute("update intents set state='frozen' where id=?",('needs:'+run_id,))
        return {**body,'sha256':digest(body),'status':'frozen'}


def readiness(registry,needs,target_ref):
    groups={}
    for need in needs:
        validate(need);slot=(need['requirement_id'],need['case_id'])
        case=groups.setdefault(slot,{'requirement_id':slot[0],'case_id':slot[1],'fixture_status':'ready','resources':[]})
        try:
            binding=registry.resolve(need['fixture_key'],need['version'],target_ref)
            with registry.tx() as db:bp=registry._blueprint(db,need['fixture_key'],need['version'])
            require(need['usage']!='write' or bp['pool']=='run','SHARED_POOL_WRITE_FORBIDDEN')
            item={'fixture_key':need['fixture_key'],'status':'ready','local_id':binding['local_id']}
        except FixtureError as e:
            case['fixture_status']='blocked';item={'fixture_key':need['fixture_key'],'status':'blocked','reason':str(e)}
        case['resources'].append(item)
    return {'status':'blocked' if any(c['fixture_status']=='blocked' for c in groups.values()) else 'ready',
            'authority':'fixture_preconditions_only','target_ref':target_ref,'cases':list(groups.values())}


def align(registry,key,version,targets,fields):
    require(isinstance(targets,list) and len(set(targets))>=2 and isinstance(fields,list) and fields,'ALIGNMENT_SCOPE_REQUIRED')
    values=[]
    for target in targets:
        b=registry.resolve(key,version,target);attrs=b['observation']['attributes']
        require(all(f in attrs for f in fields),'ALIGNMENT_ATTRIBUTE_MISSING')
        values.append({'target_ref':target,'attributes':{f:attrs[f] for f in fields}})
    differences=[f for f in fields if any(v['attributes'][f]!=values[0]['attributes'][f] for v in values[1:])]
    return {'status':'drift' if differences else 'aligned','fixture_key':key,'version':version,'compared_fields':fields,'differences':differences,'targets':values}
