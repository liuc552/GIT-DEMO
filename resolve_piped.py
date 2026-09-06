import json
import urllib.request
from pathlib import Path

VIDEO_ID = '8mQEzS-DXuE'
UA = 'Mozilla/5.0'
INSTANCES = [
    'https://pipedapi.kavin.rocks',
    'https://pipedapi.syncpundit.io',
    'https://api-piped.mha.fi',
    'https://piped-api.garudalinux.org',
    'https://api.piped.yt',
    'https://pipedapi.owo.si',
]

Path('work').mkdir(exist_ok=True)
errors = []

for base in INSTANCES:
    try:
        print('Trying Piped:', base)
        req = urllib.request.Request(f'{base}/streams/{VIDEO_ID}', headers={'User-Agent': UA, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.loads(r.read().decode('utf-8', errors='replace'))
        title = data.get('title') or ''
        streams = [x for x in (data.get('audioStreams') or []) if x.get('url')]
        if not streams:
            raise RuntimeError('no audioStreams')
        # Prefer a modest bitrate to reduce transfer while keeping speech clear.
        streams.sort(key=lambda x: int(x.get('bitrate') or 999999))
        stream = streams[0]
        media_url = stream['url']
        mime = stream.get('mimeType') or ''
        ext = '.m4a' if 'mp4' in mime else '.webm'
        out = Path('work/source' + ext)
        print('Title:', title)
        print('Audio:', stream.get('quality'), mime, 'via', media_url[:120])
        dl = urllib.request.Request(media_url, headers={'User-Agent': UA, 'Accept': '*/*'})
        with urllib.request.urlopen(dl, timeout=180) as r, out.open('wb') as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        size = out.stat().st_size
        print('Downloaded bytes:', size)
        if size < 100000:
            raise RuntimeError(f'audio too small: {size}')
        Path('piped-metadata.json').write_text(json.dumps({
            'instance': base, 'title': title, 'stream': stream
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print('PIPED_ACQUISITION_OK')
        break
    except Exception as e:
        errors.append(f'{base}: {type(e).__name__}: {e}')
        print('Failed:', type(e).__name__, e)
else:
    raise RuntimeError('all Piped instances failed:\n' + '\n'.join(errors))
