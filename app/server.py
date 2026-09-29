"""Dependency-free, read-only local reference service and JSON API."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]


def validate_data(data):
    workflows, evidence = data['workflows'], data['evidence']
    if not workflows or len({w['id'] for w in workflows}) != len(workflows):
        raise ValueError('Workflow IDs must be unique and nonempty')
    if any(not re.fullmatch(r'(WF|FW|TR|SN)-\d{3}', w['id']) for w in workflows):
        raise ValueError('Invalid workflow ID')
    for ref in evidence.values():
        if hashlib.sha256(ref['quote'].encode()).hexdigest() != ref['sha256']:
            raise ValueError(f"Evidence checksum mismatch: {ref['id']}")
    all_ids = set()
    for w in workflows:
        ids = {w['id']}
        for n in w['nodes']:
            if n['id'] in all_ids or not n['evidenceIds']:
                raise ValueError('Duplicate node or missing evidence')
            ids.add(n['id'])
            all_ids.add(n['id'])
            if n['text'] != evidence[n['evidenceIds'][0]]['quote']:
                raise ValueError('Action text must match the source verbatim')
        for item in [w, *w['nodes'], *w['edges']]:
            if not item['evidenceIds'] or any(e not in evidence for e in item['evidenceIds']):
                raise ValueError('Missing evidence reference')
        for edge in w['edges']:
            if edge['source'] not in ids or edge['target'] not in ids:
                raise ValueError('Dangling graph edge')
            if edge['kind'] not in ['contains', 'after', 'conditional']:
                raise ValueError('Unknown graph relation')
    return data


DATA = validate_data(json.loads((ROOT / 'data/workflows.json').read_text(encoding='utf-8')))
WEATHER = validate_data(json.loads((ROOT / 'data/weather/workflows.json').read_text(encoding='utf-8')))
CATALOG = [
    {'id': 'wildfire', 'name': '산불', 'subtitle': '산림청 · 산불 대응', 'prefix': 'WF'},
    {'id': 'typhoon-rain', 'name': '태풍·호우', 'subtitle': '밀양시 · 태풍·호우 및 풍수해 공통', 'prefix': 'TR / FW'},
    {'id': 'snow', 'name': '대설', 'subtitle': '밀양시 · 대설 및 풍수해 공통', 'prefix': 'SN / FW'},
]
DATASETS = {'wildfire': DATA}
for hazard in ['typhoon-rain', 'snow']:
    workflows = [w for w in WEATHER['workflows'] if hazard in w['applicability']]
    refs = {e for w in workflows for e in w['evidenceIds']}
    DATASETS[hazard] = validate_data({**WEATHER, 'workflows': workflows,
                                    'evidence': {e: WEATHER['evidence'][e] for e in refs}})



def normalize(value):
    return unicodedata.normalize('NFC', value).casefold()


def filter_workflows(query='', phase='', agency='', data=None, scope=''):
    data = DATA if data is None else data
    tokens = normalize(query).split()
    result = []
    for w in data['workflows']:
        if scope and w.get('scope', 'specific') != scope:
            continue
        if phase and phase not in w['phases']:
            continue
        if agency and agency not in w['agencies']:
            continue
        searchable = normalize(' '.join([w['id'], w['title'], *w['agencies'], *w['phases'],
            *[n['label'] + ' ' + n['text'] for n in w['nodes']],
            *[data['evidence'][e]['heading'] for e in w['evidenceIds']]]))
        if all(t in searchable for t in tokens):
            result.append(w)
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'DisasterSOP/0.2.0'

    def send(self, status, body, mime='application/json; charset=utf-8', head=False):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_HEAD(self):
        self.route(head=True)

    def do_GET(self):
        self.route()

    def route(self, head=False):
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        hazard = 'wildfire'
        if path == '/api/disasters':
            return self.send(200, {'items': CATALOG}, head=head)
        if path.startswith('/api/disasters/'):
            parts = path.split('/')
            if len(parts) < 5 or parts[3] not in DATASETS:
                return self.send(404, {'error': 'Unknown disaster'}, head=head)
            hazard = parts[3]
            path = '/api/' + '/'.join(parts[4:])
        data = DATASETS[hazard]
        if path.startswith('/manuals/'):
            parts = path.split('/')
            if len(parts) != 4 or parts[2] not in DATASETS:
                return self.send(404, {'error': 'Unknown manual'}, head=head)
            selected = DATASETS[parts[2]]
            if parts[3] == 'workflows.json':
                return self.send(200, selected, head=head)
            if parts[3] == 'source-excerpts.xml':
                file = 'data/source-excerpts.xml' if parts[2] == 'wildfire' else 'data/weather/source-excerpts.xml'
                root = ET.parse(ROOT / file).getroot()
                for excerpt in list(root):
                    if excerpt.get('id') not in selected['evidence']:
                        root.remove(excerpt)
                return self.send(200, ET.tostring(root, encoding='utf-8', xml_declaration=True), 'application/xml; charset=utf-8', head=head)
            return self.send(404, {'error': 'Unknown manual file'}, head=head)
        if path == '/health':
            return self.send(200, {'status': 'ok', 'version': data['version'], 'workflows': len(data['workflows'])}, head=head)
        if path == '/api/meta':
            return self.send(200, {**{k: data[k] for k in ['version', 'source', 'phases', 'editorialNote', 'graphNote']},
                'agencies': sorted({a for w in data['workflows'] for a in w['agencies']}),
                'workflowCount': len(data['workflows']), 'nodeCount': sum(len(w['nodes']) for w in data['workflows']),
                'evidenceCount': len(data['evidence']),
                'disaster': hazard, 'name': next(c['name'] for c in CATALOG if c['id'] == hazard),
                'commonCount': sum(w.get('scope') == 'common' for w in data['workflows'])}, head=head)
        if path == '/api/workflows':
            try:
                params = parse_qs(parsed.query, max_num_fields=10)
            except ValueError:
                return self.send(400, {'error': 'Too many query fields'}, head=head)
            if any(k not in ['q', 'phase', 'agency', 'scope'] or len(v) != 1 for k, v in params.items()):
                return self.send(400, {'error': 'Supported parameters: q, phase, agency, scope (once each)'}, head=head)
            q, phase, agency = [params.get(k, [''])[0] for k in ['q', 'phase', 'agency']]
            if len(q) > 200:
                return self.send(400, {'error': 'Search query must be 200 characters or less'}, head=head)
            if phase and phase not in data['phases']:
                return self.send(400, {'error': 'Unknown phase'}, head=head)
            if agency and agency not in {a for w in data['workflows'] for a in w['agencies']}:
                return self.send(400, {'error': 'Unknown agency'}, head=head)
            scope = params.get('scope', [''])[0]
            if scope not in ['', 'common', 'specific']:
                return self.send(400, {'error': 'Unknown scope'}, head=head)
            items = filter_workflows(q, phase, agency, data=data, scope=scope)
            return self.send(200, {'total': len(items), 'items': items}, head=head)
        if re.fullmatch(r'/api/workflows/(WF|FW|TR|SN)-\d{3}', path):
            w = next((w for w in data['workflows'] if w['id'] == path.rsplit('/', 1)[-1]), None)
            if w:
                return self.send(200, {**w, 'evidence': {e: data['evidence'][e] for e in w['evidenceIds']}}, head=head)
        if path.startswith('/api/evidence/'):
            evidence = data['evidence'].get(path.rsplit('/', 1)[-1])
            if evidence:
                return self.send(200, {**evidence, 'source': data['source']}, head=head)
        static = {'/': ('web/index.html', 'text/html; charset=utf-8'),
                  '/original': ('web/original.html', 'text/html; charset=utf-8'),
                  '/original.html': ('web/original.html', 'text/html; charset=utf-8'),
                  '/app.js': ('web/app.js', 'text/javascript; charset=utf-8'),
                  '/styles.css': ('web/styles.css', 'text/css; charset=utf-8'),
                  '/original.js': ('web/original.js', 'text/javascript; charset=utf-8'),
                  '/original.css': ('web/original.css', 'text/css; charset=utf-8'),
                  '/source-excerpts.xml': ('data/source-excerpts.xml', 'application/xml; charset=utf-8'),
                  '/workflows.json': ('data/workflows.json', 'application/json; charset=utf-8')}
        if path in static:
            file, mime = static[path]
            return self.send(200, (ROOT / file).read_bytes(), mime, head=head)
        self.send(404, {'error': 'Not found'}, head=head)


def create_server(host='127.0.0.1', port=8080):
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))
    args = parser.parse_args()
    with create_server(args.host, args.port) as server:
        print(f'Disaster SOP v0.2.0 listening on {args.host}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
