#!/usr/bin/env python3
"""Place Details, exact field mask, explicit call ceiling, terms-aware cache."""
import argparse
import urllib.parse
from datetime import timedelta, datetime
from common import (ROOT, DETAIL_MASK, PlacesClient, cache_file, cached_details, iso,
                    now, permission, plan, purge_expired, read_json, write_json, future)

def main(force=False):
    purge_expired()
    ids = sorted({r['place_id'] for r in read_json(ROOT / 'data/matches.json', {}).get('places', [])
                  if r.get('confirmed') and r.get('place_id')})
    grant = permission()
    def valid_cache(pid):
        if grant: return cached_details(pid)
        c = read_json(cache_file(pid, 'coordinates'), {})
        return c if future(c.get('expires_at')) else None
    pending = [pid for pid in ids if force or not valid_cache(pid)]
    parser = argparse.ArgumentParser(description=__doc__)
    args, execute = plan(parser, len(pending), '每个缺少有效缓存的 place_id 1 次 Details；无额外授权仅请求 id,location；完整字段可能触发较高 SKU')
    if not execute:
        return
    print('静态详情缓存授权：' + ('已配置，请自行确认其适用范围' if grant else '未配置；仅保存经纬度（30天）；其余响应在内存用后丢弃'))
    client = PlacesClient(args.max_calls)
    for pid in pending:
        detail = client.request('GET', 'places/' + urllib.parse.quote(pid, safe=''), DETAIL_MASK if grant else 'id,location')
        if detail.get('id') != pid:
            raise ValueError('Details 返回的 place_id 与请求不符；未写入缓存')
        stamp = now()
        if detail.get('location'):
            write_json(cache_file(pid, 'coordinates'), {'place_id':pid, 'location':detail['location'],
                'fetched_at':iso(stamp), 'expires_at':iso(stamp + timedelta(days=30))})
        if grant:
            # At most 24h even when a separately documented grant allows longer.
            deadline = min(stamp + timedelta(hours=24), datetime.fromisoformat(grant['expires_at']))
            write_json(cache_file(pid), {'place_id':pid, 'data':detail, 'fetched_at':iso(stamp),
                'expires_at':iso(deadline), 'permission_reference':grant['reference']})
    print(f'确认店铺 {len(ids)}；已处理 {len(pending)}；实际 API 调用 {client.calls} 次。')

if __name__ == '__main__':
    main()
