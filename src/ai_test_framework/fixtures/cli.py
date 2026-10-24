"""Fixture commands: local registration/preparation, never implicit external writes."""
import json
import sqlite3
from pathlib import Path
from .registry import Registry,FixtureError,database_path
from .inventory import inventory
from .executor import prepare
from .needs import record, freeze, readiness, align


def add_parser(commands):
    p=commands.add_parser('fixture',help='本地Fixture登记、健康、租约和离线准备；业务操作由私有Provider执行')
    p.add_argument('fixture_command',choices=['catalog','register','bind','observe','resolve','acquire','release','heartbeat','prepare','inventory','handbook','record-need','freeze-needs','readiness','align'])
    p.add_argument('--root',default='.')
    p.add_argument('--registry-root')
    p.add_argument('--input')
    p.add_argument('--output')
    p.add_argument('--key');p.add_argument('--version');p.add_argument('--target')
    return p


def handbook(registry):
    data=registry.catalog();lines=['# 测试数据使用手册','','自动从本机登记生成；密码不在此文档。健康检查不等于业务回归通过。','']
    targets={t['target_ref']:t for t in data['targets']}
    bp={(b['fixture_key'],b['version']):b for b in data['blueprints']}
    def text(v):return str(v).replace('\n',' ').replace('|','\\|')
    for b in data['bindings']:
        definition=bp[(b['key'],b['version'])];t=targets[b['target']]
        try:registry.resolve(b['key'],b['version'],b['target']);state='healthy'
        except FixtureError as e:state=str(e)
        lines += [f"## {text(definition['attributes'].get('name',b['key']))}",'',
          f"- 稳定标识：{text(b['key'])} @ {text(b['version'])}",
          f"- 环境：{text(t['stage'])}/{text(t['zone'])}；门店：{text(t['salon'])}；角色：{text(t['role'])}",
          f"- 实体：{text(definition['entity'])}；本地ID：{text(b['local_id'])}；用途池：{definition['pool']}",
          f"- 数据状态：{state}；回归状态须看对应Case收据。",'']
    if not data['bindings']:lines += ['暂无已登记实例；不能将蓝图示例当成可用数据。']
    return '\n'.join(lines)+'\n'


def run(args):
    try:
        data=json.loads(Path(args.input).read_text()) if args.input else {}
        if args.fixture_command=='inventory':result=inventory(args.root,args.registry_root)
        else:
            r=Registry(database_path(args.root));op=args.fixture_command
            if op=='catalog':result=r.catalog()
            elif op=='register':
                for t in data.get('targets',[]):r.add_target(t)
                if data.get('blueprints'):r.add_blueprints(data['blueprints'])
                result={'status':'registered','business_writes':0}
            elif op=='resolve':result={'status':'ready',**r.resolve(args.key,args.version,args.target)}
            elif op=='bind':r.bind(data['fixture_key'],data['version'],data['target_ref'],data['local_id']);result={'status':'bound_unverified'}
            elif op=='observe':result={'status':'ready',**r.observe(data['fixture_key'],data['version'],data['target_ref'],data['observation'],data.get('ttl',300))}
            elif op=='acquire':result=r.acquire(data['requests'],data['run_id'],data.get('ttl',300))
            elif op=='release':result=r.release(data['lease_id'],data['run_id'],data['observations'])
            elif op=='heartbeat':r.heartbeat(data['lease_id'],data['run_id'],data.get('ttl',300));result={'status':'renewed'}
            elif op=='prepare':result=prepare(r,data['needs'],data['target_ref'],data['capabilities'])
            elif op=='record-need':result=record(r,data['run_id'],data['need'])
            elif op=='freeze-needs':result=freeze(r,data['run_id'])
            elif op=='readiness':result=readiness(r,data['needs'],data['target_ref'])
            elif op=='align':result=align(r,data['fixture_key'],data['version'],data['targets'],data['fields'])
            elif op=='handbook':result={'status':'generated','markdown':handbook(r)}
        if args.output:
            p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(result['markdown'] if args.fixture_command=='handbook' else json.dumps(result,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600)
        return result
    except FixtureError as e:return {'status':'blocked','code':str(e)}
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):return {'status':'blocked','code':'FIXTURE_INPUT_OR_STORAGE_INVALID'}
