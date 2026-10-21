#!/usr/bin/env python3
"""Conservative name+address matching; default is a zero-request dry run."""
import argparse
import re
import unicodedata
from common import ROOT, PlacesClient, SEARCH_MASK, fingerprint, plan, read_json, write_csv, write_json

ALIASES = {'street':'st', 'road':'rd', 'avenue':'ave', 'boulevard':'blvd', 'drive':'dr',
           'ontario':'on', 'east':'e', 'west':'w', 'north':'n', 'south':'s'}

def normalize(text, address=False):
    value = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    tokens = re.findall(r'\w+', value)
    return ' '.join(ALIASES.get(t, t) if address else t for t in tokens)

def classify(raw, response):
    candidates = []
    for c in response.get('places', []):
        name_ok = normalize(raw['name']) == normalize(c.get('displayName', {}).get('text', ''))
        address_ok = normalize(raw['address'], True) == normalize(c.get('formattedAddress', ''), True)
        # Only IDs and comparison outcomes persist. API names/addresses are transient.
        print(f"候选 {c['id']}: {c.get('displayName', {}).get('text', '')} | {c.get('formattedAddress', '')} | name={name_ok}, address={address_ok}")
        candidates.append({'place_id': c['id'], 'name_exact': name_ok, 'address_exact': address_ok})
    exact = len(candidates) == 1 and candidates[0]['name_exact'] and candidates[0]['address_exact']
    exact = exact and not response.get('nextPageToken')
    return {'raw_id': raw['raw_id'], 'query_hash': fingerprint([raw['name'], raw['address']]),
        'place_id': candidates[0]['place_id'] if exact else None, 'confirmed': bool(exact),
        'needs_review': bool(candidates) and not exact, 'unresolved': not candidates,
        'candidates': candidates, 'more_candidates': bool(response.get('nextPageToken')),
        'match_method': 'exact_name_and_address' if exact else None}

def main():
    raw = read_json(ROOT / 'data/places_raw.json', {}).get('places', [])
    existing = {r['raw_id']: r for r in read_json(ROOT / 'data/matches.json', {}).get('places', [])}
    pending = [r for r in raw if existing.get(r['raw_id'], {}).get('query_hash') != fingerprint([r['name'], r['address']])]
    parser = argparse.ArgumentParser(description=__doc__)
    args, execute = plan(parser, len(pending), '每个未缓存输入 1 次 Text Search；最多 20 个候选，不翻页；出现下一页时必须人工复核')
    if not execute:
        return
    client = PlacesClient(args.max_calls)
    for r in pending:
        response = client.request('POST', 'places:searchText', SEARCH_MASK,
            {'textQuery': r['name'] + ' ' + r['address'], 'pageSize': 20, 'languageCode': 'en', 'regionCode': 'CA'})
        existing[r['raw_id']] = classify(r, response)
        write_json(ROOT / 'data/matches.json', {'places': [existing[x['raw_id']] for x in raw if x['raw_id'] in existing]})
    records = [existing[x['raw_id']] for x in raw]
    write_json(ROOT / 'data/matches.json', {'places': records})
    unresolved = [r for r in raw if existing[r['raw_id']]['unresolved']]
    write_csv(ROOT / 'data/unresolved.csv', ['raw_id','name','address','maps_url','owner_note'], unresolved)
    review_path = ROOT / 'data/match_review.csv'
    # Never overwrite manual choices during a resume.
    from common import read_csv
    previous = {r['raw_id']: r for r in read_csv(review_path)} if review_path.exists() else {}
    review = []
    for r in raw:
        m = existing[r['raw_id']]
        if m['needs_review'] or m['unresolved']:
            review.append(previous.get(r['raw_id'], {'raw_id':r['raw_id'], 'name':r['name'],
                'candidate_ids':' | '.join(c['place_id'] for c in m['candidates']),
                'selected_place_id':'', 'confirm_name_and_address':''}))
    write_csv(review_path, ['raw_id','name','candidate_ids','selected_place_id','confirm_name_and_address'], review)
    print(f"已确认 {sum(m['confirmed'] for m in records)}；needs_review {sum(m['needs_review'] for m in records)}；unresolved {len(unresolved)}；实际 API {client.calls} 次。")

if __name__ == '__main__':
    main()
