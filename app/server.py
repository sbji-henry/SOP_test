"""Dependency-free, read-only local reference service and JSON API."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import parse_qs, urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]


def validate_data(data):
    workflows, evidence = data['workflows'], data['evidence']
    if [w['id'] for w in workflows] != [f'WF-{i:03}' for i in range(1, 13)]:
        raise ValueError('WF-001 through WF-012 must be present exactly once')
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


def normalize(value):
    return unicodedata.normalize('NFC', value).casefold()


def filter_workflows(query='', phase='', agency=''):
    tokens = normalize(query).split()
    result = []
    for w in DATA['workflows']:
        if phase and phase not in w['phases']:
            continue
        if agency and agency not in w['agencies']:
            continue
        searchable = normalize(' '.join([w['id'], w['title'], *w['agencies'], *w['phases'],
            *[n['label'] + ' ' + n['text'] for n in w['nodes']],
            *[DATA['evidence'][e]['heading'] for e in w['evidenceIds']]]))
        if all(t in searchable for t in tokens):
            result.append(w)
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'WildfireSOP/0.1.0'

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
        if path == '/health':
            return self.send(200, {'status': 'ok', 'version': DATA['version'], 'workflows': 12}, head=head)
        if path == '/api/meta':
            return self.send(200, {**{k: DATA[k] for k in ['version', 'source', 'phases', 'editorialNote', 'graphNote']},
                'agencies': sorted({a for w in DATA['workflows'] for a in w['agencies']}),
                'workflowCount': len(DATA['workflows']), 'nodeCount': sum(len(w['nodes']) for w in DATA['workflows']),
                'evidenceCount': len(DATA['evidence'])}, head=head)
        if path == '/api/workflows':
            try:
                params = parse_qs(parsed.query, max_num_fields=10)
            except ValueError:
                return self.send(400, {'error': 'Too many query fields'}, head=head)
            if any(k not in ['q', 'phase', 'agency'] or len(v) != 1 for k, v in params.items()):
                return self.send(400, {'error': 'Supported parameters: q, phase, agency (once each)'}, head=head)
            q, phase, agency = [params.get(k, [''])[0] for k in ['q', 'phase', 'agency']]
            if len(q) > 200:
                return self.send(400, {'error': 'Search query must be 200 characters or less'}, head=head)
            if phase and phase not in DATA['phases']:
                return self.send(400, {'error': 'Unknown phase'}, head=head)
            if agency and agency not in {a for w in DATA['workflows'] for a in w['agencies']}:
                return self.send(400, {'error': 'Unknown agency'}, head=head)
            items = filter_workflows(q, phase, agency)
            return self.send(200, {'total': len(items), 'items': items}, head=head)
        if re.fullmatch(r'/api/workflows/WF-\d{3}', path):
            w = next((w for w in DATA['workflows'] if w['id'] == path.rsplit('/', 1)[-1]), None)
            if w:
                return self.send(200, {**w, 'evidence': {e: DATA['evidence'][e] for e in w['evidenceIds']}}, head=head)
        if path.startswith('/api/evidence/'):
            evidence = DATA['evidence'].get(path.rsplit('/', 1)[-1])
            if evidence:
                return self.send(200, {**evidence, 'source': DATA['source']}, head=head)
        static = {'/': ('web/index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('web/app.js', 'text/javascript; charset=utf-8'),
                  '/styles.css': ('web/styles.css', 'text/css; charset=utf-8'),
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
        print(f'Wildfire SOP v0.1.0 listening on {args.host}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
