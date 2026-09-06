import json
import urllib.parse
import urllib.request
from pathlib import Path

URL = next(
    line.strip()
    for line in Path('urls.txt').read_text(encoding='utf-8').splitlines()
    if line.strip() and not line.lstrip().startswith('#')
)

api = 'https://api.bugpk.com/api/douyin?' + urllib.parse.urlencode({'url': URL})
req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=60) as r:
    payload = json.loads(r.read().decode('utf-8'))

Path('resolver-response.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
if payload.get('code') != 200 or not payload.get('data'):
    raise RuntimeError(f"resolver failed: {payload}")

data = payload['data']
media = data.get('url')
if not media:
    backups = data.get('video_backup') or []
    if isinstance(backups, str):
        backups = [backups]
    media = backups[0] if backups else None
if not media:
    raise RuntimeError(f"resolver returned no video URL: {payload}")

print('Resolver title:', data.get('title') or data.get('desc'))
print('Resolver author:', (data.get('author') or {}).get('name') if isinstance(data.get('author'), dict) else data.get('author'))
print('Media URL:', media[:180])

Path('work').mkdir(exist_ok=True)
out = Path('work/source.mp4')
request = urllib.request.Request(media, headers={
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://www.douyin.com/'
})
with urllib.request.urlopen(request, timeout=120) as r, out.open('wb') as f:
    while True:
        chunk = r.read(1024 * 1024)
        if not chunk:
            break
        f.write(chunk)
print('Downloaded bytes:', out.stat().st_size)
if out.stat().st_size < 100000:
    raise RuntimeError('downloaded media is unexpectedly small')
