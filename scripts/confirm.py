#!/usr/bin/env python3
"""Apply explicit human selections, without API requests."""
from common import ROOT, read_csv, read_json, write_csv, write_json

def main():
    records = read_json(ROOT / 'data/matches.json', {}).get('places', [])
    by_id = {r['raw_id']: r for r in records}
    path = ROOT / 'data/match_review.csv'
    selected = read_csv(path) if path.exists() else []
    changes = []
    for row in selected:
        pid = row.get('selected_place_id', '').strip()
        if not pid:
            continue
        if row['raw_id'] not in by_id:
            raise ValueError('复核表包含过期 raw_id，请重新运行 match')
        if row.get('confirm_name_and_address', '').strip().lower() != 'yes':
            raise ValueError(f"{row['name']}：核对名称和完整地址后，确认列填 yes")
        if not pid.replace('_','').replace('-','').isalnum():
            raise ValueError('place_id 格式无效')
        changes.append((by_id[row['raw_id']], pid))
    for item, pid in changes:
        item.update(place_id=pid, confirmed=True, needs_review=False, unresolved=False, match_method='human_confirmed')
    write_json(ROOT / 'data/matches.json', {'places':records})
    raw = read_json(ROOT / 'data/places_raw.json', {}).get('places', [])
    write_csv(ROOT / 'data/unresolved.csv', ['raw_id','name','address','maps_url','owner_note'],
        [r for r in raw if by_id.get(r['raw_id'], {}).get('unresolved')])
    print(f'人工确认 {len(changes)} 条；API 调用 0 次。')

if __name__ == '__main__':
    main()
