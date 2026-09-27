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
    assert '재난 대응 SOP' in response.read().decode()
for hazard, count, prefix in [('typhoon-rain', 19, 'TR-'), ('snow', 15, 'SN-')]:
    items = get(f'/api/disasters/{hazard}/workflows')['items']
    assert len(items) == count and any(w['id'].startswith(prefix) for w in items)
    assert get(f'/api/disasters/{hazard}/workflows?scope=common')['total'] == 11
print('PASS: health, separate hazard workflows, shared flood tasks, evidence, search, UI entry')
