#!/usr/bin/env python3
"""Prepare Pages artifact without checking personal/API data into git history."""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, future, iso, read_json

# Explicit allowlist: secrets and Python/source data can never enter the web artifact.
ASSETS=['index.html','style.css','app.mjs','logic.mjs','config.json','favicon.svg','privacy.html','terms.html']

def sanitize(payload):
    if not isinstance(payload,dict) or payload.get('schema_version')!=1 or not isinstance(payload.get('places'),list):
        raise ValueError('站点数据结构无效')
    payload=json.loads(json.dumps(payload))
    for p in payload['places']:
        if not isinstance(p,dict) or not p.get('place_id') or not p.get('name'):
            raise ValueError('每家店必须有 place_id 和 name')
        if p.get('google'):
            g=p['google']
            if not g.get('permission_reference'):
                raise ValueError('Google 非坐标字段缺少静态发布授权依据；不打包')
            if not future(g.get('expires_at')): p['google']=None
        if p.get('coordinates') and not future(p['coordinates'].get('expires_at')):
            p['coordinates']=None
    return payload

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/pages')
    parser.add_argument('--ci',action='store_true',help='Use FOOD_DATA_JSON secret or explicit empty state')
    args=parser.parse_args()
    if args.ci:
        value=os.environ.get('FOOD_DATA_JSON','')
        payload=json.loads(value) if value.strip() else read_json(ROOT/'site/data.empty.json')
    else:
        payload=read_json(ROOT/'site/data.json',read_json(ROOT/'site/data.empty.json'))
    payload=sanitize(payload)
    if not payload['places']: payload['generated_at']=iso()
    args.output.mkdir(parents=True,exist_ok=True)
    for file in args.output.iterdir():
        if file.is_file(): file.unlink()
        else: shutil.rmtree(file)
    for name in ASSETS: shutil.copyfile(ROOT/'site'/name,args.output/name)
    (args.output/'data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.output/'.nojekyll').touch()
    print(f'Pages artifact: {args.output}; places={len(payload["places"])}; API 调用 0 次。')

if __name__=='__main__': main()
