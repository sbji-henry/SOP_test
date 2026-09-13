"""Run against the real Docker service: python scripts/smoke.py [URL]."""
import json
import sys
from urllib.request import urlopen
from urllib.parse import urlencode

base = sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8080'

def get(path):
    with urlopen(base + path, timeout=10) as response:
        return json.load(response)

assert get('/health')['status'] == 'ok'
items = get('/api/workflows')['items']
assert len(items) == 12
for w in items:
    detail = get('/api/workflows/' + w['id'])
    assert detail['nodes'] and detail['evidence']
assert [w['id'] for w in get('/api/workflows?' + urlencode({'q':'잔불'}))['items']] == ['WF-011']
with urlopen(base + '/', timeout=10) as response:
    assert '산불 대응 SOP' in response.read().decode()
print('PASS: health, 12 workflow details, evidence, Korean search, UI entry')
