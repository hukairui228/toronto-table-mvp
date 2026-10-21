#!/usr/bin/env python3
"""Maintain empty human columns and merge without coercing unknowns to zero/false."""
import argparse
import math
from common import (ROOT, HUMAN_COLUMNS, SCENARIOS, cache_file, cached_details, future,
                    iso, purge_expired, read_csv, read_json, write_csv, write_json)

def nullable_bool(value):
    value = (value or '').strip().lower()
    if value == '': return None
    if value in ('1','true','yes','是'): return True
    if value in ('0','false','no','否'): return False
    raise ValueError(f'无效布尔值 {value!r}；使用 yes/no 或留空')

def number(value, minimum=0, maximum=None, integer=False):
    if not (value or '').strip(): return None
    result = float(value)
    if not math.isfinite(result) or result < minimum or (maximum is not None and result > maximum) or (integer and result != int(result)):
        raise ValueError(f'无效数值 {value!r}')
    return int(result) if integer else result

def human_data(row, source):
    scenarios = [x.strip() for x in (row.get('scenario') or '').split('|') if x.strip()]
    if any(x not in SCENARIOS for x in scenarios):
        raise ValueError('scenario 仅接受：' + ' / '.join(SCENARIOS) + '；多选用 | 分隔')
    return {'owner_note':source.get('owner_note',''),
        **{k:(row.get(k) or '').strip() or None for k in ('my_take','best_dish','cuisine_detail')},
        'scenario': list(dict.fromkeys(scenarios)) or None,
        'spicy':number(row.get('spicy'), 0, 3, True),
        'price_per_person_cad':number(row.get('price_per_person_cad')),
        'skip':nullable_bool(row.get('skip'))}

def merge_rows(raw, matches, human, details, coordinates=None):
    matches = {r['raw_id']:r for r in matches}
    humans = {}
    for h in human:
        pid = h.get('place_id')
        if pid in humans: raise ValueError('human_fields.csv 中 place_id 重复')
        humans[pid] = h
    output = []
    for source in raw:
        match = matches.get(source['raw_id'], {})
        pid = match.get('place_id')
        if not pid or not match.get('confirmed'): continue
        if any(p['place_id'] == pid for p in output):
            raise ValueError('多行输入确认到同一家店，请先人工去重，避免覆盖备注')
        h = humans.get(pid, {})
        google = details.get(pid)
        coord = (coordinates or {}).get(pid)
        output.append({'place_id':pid, 'name':source['name'], 'address':source['address'],
            'maps_url':source['maps_url'], **human_data(h,source),
            'google':google, 'coordinates':coord})
    return output

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--init-human', action='store_true', help='Create/update blank rows, preserving all edited human fields')
    args = p.parse_args()
    purge_expired()
    raw = read_json(ROOT / 'data/places_raw.json', {}).get('places', [])
    matches = read_json(ROOT / 'data/matches.json', {}).get('places', [])
    path = ROOT / 'data/human_fields.csv'
    human = read_csv(path) if path.exists() else []
    if args.init_human:
        old = {r['place_id']:r for r in human}
        source = {r['raw_id']:r for r in raw}
        human = []
        for m in matches:
            if m.get('confirmed'):
                r = source[m['raw_id']]
                h = {c:'' for c in HUMAN_COLUMNS}
                h.update(old.get(m['place_id'], {}))
                h.update(place_id=m['place_id'], name=r['name'], owner_note=r['owner_note'])
                human.append(h)
        write_csv(path, HUMAN_COLUMNS, human)
        print(f'人工表：{len(human)} 行；owner_note 从原输入原样恢复；其余已填字段保留。')
    details, coords = {}, {}
    for m in matches:
        if m.get('confirmed') and m.get('place_id'):
            pid = m['place_id']
            d = cached_details(pid)
            if d: details[pid] = d
            c = read_json(cache_file(pid, 'coordinates'))
            if c and future(c.get('expires_at')): coords[pid] = c
    places = merge_rows(raw,matches,human,details,coords)
    write_json(ROOT / 'site/data.json', {'schema_version':1,'generated_at':iso(), 'places':places})
    print(f'写入 site/data.json：{len(places)} 家；未知字段保留 null。API 调用 0 次。')

if __name__ == '__main__':
    main()
