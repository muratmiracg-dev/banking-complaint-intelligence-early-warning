import json
import socket
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from complaint_intelligence.config import ROOT


class LocalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.base=f'http://127.0.0.1:{cls.port}'
        cls.process=subprocess.Popen([sys.executable,'-m','complaint_intelligence','serve','--port',str(cls.port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with urlopen(cls.base+'/api/health',timeout=.2) as r:
                    if r.status==200:return
            except OSError:time.sleep(.1)
        cls.process.terminate()
        raise RuntimeError('Local API did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=5)

    def test_health_and_search(self):
        with urlopen(self.base+'/api/search?q=account',timeout=5) as r:
            result=json.load(r)
            self.assertGreater(result['total'],0)
            self.assertLessEqual(len(result['records']),100)
            self.assertTrue(all('narrative' not in row for row in result['records']))

    def test_classify(self):
        request=Request(self.base+'/api/classify',data=json.dumps({'text':'My checking account was closed without notice and I cannot access my money.'}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=5) as r:
            self.assertIn('product',json.load(r))

    def test_foreign_origin_is_rejected(self):
        request=Request(self.base+'/api/classify',data=b'{}',headers={'Origin':'https://untrusted.example'})
        with self.assertRaises(HTTPError) as e:urlopen(request,timeout=5)
        self.assertEqual(e.exception.code,403)

    def test_host_header_is_checked(self):
        request=Request(self.base+'/api/health',headers={'Host':'attacker.example'})
        with self.assertRaises(HTTPError) as e:urlopen(request,timeout=5)
        self.assertEqual(e.exception.code,403)

    def test_traversal_does_not_expose_data(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.base+'/../data/processed/cohort.csv',timeout=5)
        self.assertEqual(e.exception.code,404)

    def test_invalid_json_returns_400(self):
        with self.assertRaises(HTTPError) as e:urlopen(Request(self.base+'/api/classify',data=b'not json'),timeout=5)
        self.assertEqual(e.exception.code,400)
