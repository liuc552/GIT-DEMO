import json
import urllib.parse
import urllib.request
from pathlib import Path

URL = next(
    line.strip()
    for line in Path('urls.txt').read_text(encoding='utf-8').splitlines()
    if line.strip() and not line.lstrip().startswith('#')
)

RESOLVERS = [
    ('bugpk', 'https://api.bugpk.com/api/douyin'),
    ('mxin', 'https://api.mxin.moe/api/v1/douyin'),
    ('jxcxin', 'https://apis.jxcxin.cn/api/douyin'),
    ('777nx', 'https://api.777nx.cn/api/douyin/'),
]

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36'
OUT = Path('work/source.mp4')
OUT.parent.mkdir(exist_ok=True)
logs = []


def request_json(base):
    api = base + ('&' if '?' in base else '?') + urllib.parse.urlencode({'url': URL})
    req = urllib.request.Request(api, headers={'User-Agent': UA, 'Accept': 'application/json,text/plain,*/*'})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', errors='replace'))


def extract_media(name, payload):
    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = {}
    candidates = [
        data.get('url'),
        data.get('video_url'),
        data.get('play_url'),
        payload.get('url') if isinstance(payload, dict) else None,
    ]
    backups = data.get('video_backup') or data.get('backup_url') or []
    if isinstance(backups, str):
        backups = [backups]
    if isinstance(backups, list):
        candidates.extend(backups)
    for item in candidates:
        if isinstance(item, str) and item.startswith(('http://', 'https://')):
            return item
    return None


def download(media):
    if media.startswith('http://'):
        media = 'https://' + media[len('http://'):]
    req = urllib.request.Request(media, headers={
        'User-Agent': UA,
        'Referer': 'https://www.douyin.com/',
        'Accept': '*/*',
    })
    if OUT.exists():
        OUT.unlink()
    with urllib.request.urlopen(req, timeout=120) as r, OUT.open('wb') as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return OUT.stat().st_size


for name, base in RESOLVERS:
    try:
        print(f'Trying resolver: {name}')
        payload = request_json(base)
        Path(f'resolver-{name}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        media = extract_media(name, payload)
        if not media:
            raise RuntimeError(f'no media URL in response: {str(payload)[:500]}')
        print(f'{name} media URL: {media[:180]}')
        size = download(media)
        print(f'{name} downloaded bytes: {size}')
        if size < 100000:
            raise RuntimeError(f'media unexpectedly small: {size}')
        print(f'ACQUISITION_OK resolver={name}')
        break
    except Exception as e:
        logs.append(f'{name}: {type(e).__name__}: {e}')
        print(f'{name} failed: {type(e).__name__}: {e}')
else:
    raise RuntimeError('all resolvers failed:\n' + '\n'.join(logs))
