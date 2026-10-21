"""Shared stdlib-only helpers. No key is ever included in a URL or written to disk."""
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ['一个人', '约会', '聚餐', '赶时间', '深夜']
HUMAN_COLUMNS = ['place_id', 'name', 'owner_note', 'my_take', 'best_dish', 'cuisine_detail',
                 'scenario', 'spicy', 'price_per_person_cad', 'skip']
DETAIL_MASK = ','.join(['id', 'formattedAddress', 'location', 'regularOpeningHours',
    'currentOpeningHours', 'priceLevel', 'rating', 'userRatingCount', 'types',
    'addressComponents', 'attributions', 'businessStatus'])
SEARCH_MASK = 'places.id,places.displayName,places.formattedAddress,nextPageToken'

def now():
    return datetime.now(timezone.utc)

def iso(value=None):
    return (value or now()).isoformat()

def read_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(p)

def write_csv(path, columns, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def future(value):
    try:
        return datetime.fromisoformat(value) > now()
    except (TypeError, ValueError):
        return False

def cache_file(place_id, kind='details'):
    return ROOT / 'data/cache' / kind / (hashlib.sha256(place_id.encode()).hexdigest() + '.json')

def permission():
    """Default terms do NOT license a static export of ratings/hours/prices."""
    p = read_json(ROOT / 'data/cache_permission.json', {})
    if p.get('reference') and future(p.get('expires_at')) and p.get('allows_static_places_content') is True:
        return p
    return None

def cached_details(place_id):
    path = cache_file(place_id)
    value = read_json(path, {})
    if value and (not permission() or not future(value.get('expires_at'))):
        path.unlink(missing_ok=True)
        return None
    return value or None

def purge_expired():
    removed = 0
    for kind in ('details', 'coordinates'):
        for p in (ROOT / 'data/cache' / kind).glob('*.json'):
            item = read_json(p, {})
            if not future(item.get('expires_at')) or (kind == 'details' and not permission()):
                p.unlink()
                removed += 1
    return removed

def plan(parser, count, description):
    parser.add_argument('--execute', action='store_true', help='Only after user confirms the printed API plan')
    parser.add_argument('--max-calls', type=int, default=0, help='Explicit approved maximum; no retries are hidden')
    args = parser.parse_args()
    print(f'预计 API 调用次数：{count}；{description}；自动重试：0。')
    if not args.execute:
        print('仅预览，未发起 API 请求。确认后使用 --execute --max-calls N。')
        return args, False
    if count > args.max_calls:
        parser.error('预计调用次数超过已批准的 --max-calls，未调用 API。')
    if count and not os.getenv('GOOGLE_PLACES_API_KEY'):
        parser.error('缺少环境变量 GOOGLE_PLACES_API_KEY；不会从代码或网页读取 key。')
    return args, True

class PlacesClient:
    def __init__(self, max_calls, interval=0.3):
        self.max_calls, self.calls, self.interval, self.last = max_calls, 0, interval, 0

    def request(self, method, resource, mask, payload=None):
        if self.calls >= self.max_calls:
            raise RuntimeError('已达到批准的 API 调用上限')
        time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
        key = os.environ.get('GOOGLE_PLACES_API_KEY')
        if not key:
            raise RuntimeError('缺少 GOOGLE_PLACES_API_KEY')
        req = urllib.request.Request('https://places.googleapis.com/v1/' + resource,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': key, 'X-Goog-FieldMask': mask},
            method=method)
        self.calls += 1
        self.last = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not echo response bodies: some upstream diagnostics may contain credentials.
            raise RuntimeError(f'Places API HTTP {exc.code}；停止，无自动重试') from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('Places API 网络错误；停止，无自动重试') from None
