import copy
import hashlib
import json
from pathlib import Path
import threading
import unittest
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from app.server import DATA, create_server, filter_workflows, validate_data
from scripts.build_data import paragraph_text


class SourceIntegrityTests(unittest.TestCase):
    def test_every_action_matches_preserved_xml(self):
        root = ET.parse(Path(__file__).resolve().parents[1] / 'data/source-excerpts.xml').getroot()
        self.assertEqual(root.get('sourceSha256'), DATA['source']['sha256'])
        excerpts = {e.get('id'): paragraph_text(e[0]) for e in root}
        self.assertEqual(set(excerpts), set(DATA['evidence']))
        for w in DATA['workflows']:
            self.assertGreaterEqual(len(w['nodes']), 3)
            for n in w['nodes']:
                for eid in n['evidenceIds']:
                    self.assertEqual(n['text'], excerpts[eid], n['id'])
                    self.assertEqual(DATA['evidence'][eid]['sha256'], hashlib.sha256(excerpts[eid].encode()).hexdigest())

    def test_inline_control_tail_retains_critical_condition(self):
        evidence = DATA['evidence']['S5-E346']['quote']
        self.assertIn('사망사고 등 인명피해 시 중수본 가동', evidence)
        self.assertIn('차장, 실‧국장 유선보고', DATA['evidence']['S5-E423']['quote'])

    def test_no_invented_sequence_between_workflows(self):
        edges = [e for w in DATA['workflows'] for e in w['edges'] if e['kind'] != 'contains']
        self.assertEqual(len(edges), 2)
        for e in edges:
            self.assertEqual(e['source'][:6], e['target'][:6])
            self.assertTrue(e['evidenceIds'])
        self.assertIn('잔불 진화 후', DATA['evidence']['S3-E1302']['quote'])

    def test_tampering_and_dangling_edges_fail_closed(self):
        for mutate in [lambda d: d['workflows'][0]['nodes'][0].update(text='invented action'),
                       lambda d: d['workflows'][0]['edges'][0].update(target='missing'),
                       lambda d: d['workflows'][0]['nodes'][0].update(evidenceIds=[]),
                       lambda d: d['evidence']['S3-E1302'].update(quote='tampered')]:
            data = copy.deepcopy(DATA)
            mutate(data)
            with self.assertRaises(ValueError):
                validate_data(data)

    def test_search_korean_normalization_and_intersection(self):
        self.assertEqual([w['id'] for w in filter_workflows('wf-012')], ['WF-012'])
        self.assertEqual([w['id'] for w in filter_workflows('잔불')], ['WF-011'])
        self.assertEqual(filter_workflows(unicodedata.normalize('NFD', '잔불')), filter_workflows('잔불'))
        self.assertEqual(filter_workflows('잔불', '수습·복구'), [])
        self.assertEqual([w['id'] for w in filter_workflows('오보', '초기 대응', '대변인')], ['WF-010'])
        self.assertEqual(filter_workflows('<script>alert(1)</script>'), [])


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, path):
        return urlopen(self.base + path, timeout=5)

    def test_health_and_metadata(self):
        with self.get('/health') as response:
            self.assertEqual(json.load(response)['status'], 'ok')
        with self.get('/api/meta') as response:
            meta = json.load(response)
        self.assertEqual(meta['workflowCount'], 12)
        self.assertEqual(meta['nodeCount'], 51)

    def test_list_and_all_details_have_resolvable_evidence(self):
        with self.get('/api/workflows') as response:
            items = json.load(response)['items']
        self.assertEqual(len(items), 12)
        for w in items:
            with self.get('/api/workflows/' + w['id']) as response:
                detail = json.load(response)
            for n in detail['nodes']:
                self.assertTrue(set(n['evidenceIds']) <= set(detail['evidence']))
        with self.get('/api/evidence/S3-E1302') as response:
            self.assertEqual(json.load(response)['source']['edition'], '2026. 6.')

    def test_combined_search_and_empty_result(self):
        with self.get('/api/workflows?' + urlencode({'q':'CBS', 'phase':'비상 대응'})) as response:
            self.assertEqual([w['id'] for w in json.load(response)['items']], ['WF-007'])
        with self.get('/api/workflows?q=zzzzzz') as response:
            self.assertEqual(json.load(response), {'total': 0, 'items': []})

    def test_invalid_requests(self):
        for path, status in [('/api/workflows/WF-999',404),('/api/evidence/missing',404),
             ('/api/workflows?phase=unknown',400),('/api/workflows?agency=unknown',400),
             ('/api/workflows?q='+'x'*201,400),('/api/workflows?q=a&q=b',400),
             ('/api/workflows?bad=a',400),('/../app/server.py',404),('/%2e%2e/app/server.py',404),
             ('/.git/config',404),('/data/workflows.json',404)]:
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as error:
                    self.get(path)
                self.assertEqual(error.exception.code, status)

    def test_static_headers_head_and_write_rejected(self):
        with self.get('/') as response:
            self.assertIn('Workflow Explorer', response.read().decode())
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
            self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])
        with urlopen(Request(self.base+'/app.js', method='HEAD'), timeout=5) as response:
            self.assertEqual(response.read(), b'')
            self.assertGreater(int(response.headers['Content-Length']), 100)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+'/api/workflows', data=b'{}', method='POST'), timeout=5)
        self.assertEqual(error.exception.code, 501)


if __name__ == '__main__':
    unittest.main()
