#!/usr/bin/env python3
"""Inspect actual headers/first 5 rows before parsing. Preserves owner_note verbatim."""
import argparse
import csv
import json
from pathlib import Path
from common import ROOT, fingerprint, write_json

REQUIRED = ['name', 'address', 'maps_url', 'owner_note']

def parse(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(f, dialect))
    if not rows:
        raise ValueError('CSV 没有表头')
    print('实际表头：' + json.dumps(rows[0], ensure_ascii=False))
    print('前 5 行：' + json.dumps(rows[1:6], ensure_ascii=False))
    headers = [h.strip().lower() for h in rows[0]]
    if len(set(headers)) != len(headers) or not set(REQUIRED).issubset(headers):
        raise ValueError('表头必须包含唯一的 name,address,maps_url,owner_note')
    result, seen = [], set()
    for line, row in enumerate(rows[1:], 2):
        if not row or all(not x.strip() for x in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f'第 {line} 行列数不符，请正确引用含逗号/换行的字段；未自动修补')
        item = dict(zip(headers, row))
        # Notes are never stripped, translated, normalized or rewritten.
        place = {k: item[k] if k == 'owner_note' else item[k].strip() for k in REQUIRED}
        if not place['name'] or not place['address']:
            raise ValueError(f'第 {line} 行缺少店名或地址')
        place['raw_id'] = fingerprint([place[k] for k in ['name', 'address', 'maps_url']])[:16]
        if place['raw_id'] in seen:
            raise ValueError(f'第 {line} 行重复，请人工去重')
        seen.add(place['raw_id'])
        place['source_line'] = line
        result.append(place)
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, default=ROOT / 'data/raw/places.csv')
    args = p.parse_args()
    try:
        places = parse(args.input)
        write_json(ROOT / 'data/places_raw.json', {'places': places})
        print(f'写入 data/places_raw.json：{len(places)} 家店。')
    except (ValueError, OSError) as exc:
        p.exit(1, str(exc) + '\n')
