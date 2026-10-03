"""Loopback-only workbench; no uploads, remote execution, or pickle loading."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from .config import ROOT
from .model import infer


def serve(port=8765):
    web = (ROOT/'web').resolve()
    model = json.loads((ROOT/'artifacts/model.json').read_text())
    records_path = ROOT/'artifacts/local/records.json'
    records = json.loads(records_path.read_text()) if records_path.exists() else json.loads((ROOT/'artifacts/report.json').read_text())['records']

    class Handler(BaseHTTPRequestHandler):
        def send(self, value, status=200, kind='application/json; charset=utf-8'):
            body = value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            return self.headers.get('Host','') in {f'127.0.0.1:{port}',f'localhost:{port}'}

        def do_GET(self):
            if not self.allowed():
                return self.send({'error':'Invalid host'},403)
            parsed = urlparse(self.path)
            if parsed.path == '/api/health':
                return self.send({'status':'ok','records':len(records),'full_local_data':records_path.exists()})
            if parsed.path == '/api/search':
                params = parse_qs(parsed.query)
                q = params.get('q',[''])[0][:200].casefold()
                product = params.get('product',[''])[0]
                results = [r for r in records if (not product or r['product']==product) and q in ' '.join(str(r.get(k,'')) for k in ['id','company','issue','narrative','excerpt']).casefold()]
                return self.send({'total':len(results),'records':[{k:v for k,v in r.items() if k!='narrative'} for r in results[-100:][::-1]]})
            path = (web / (parsed.path.lstrip('/') or 'index.html')).resolve()
            if not path.is_relative_to(web) or not path.is_file():
                return self.send({'error':'Not found'},404)
            types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}
            if path.suffix not in types:
                return self.send({'error':'Not found'},404)
            return self.send(path.read_bytes(),kind=types[path.suffix])

        def do_POST(self):
            if not self.allowed() or self.headers.get('Origin') not in {None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'}:
                return self.send({'error':'Invalid origin or host'},403)
            if self.path != '/api/classify':
                return self.send({'error':'Not found'},404)
            try:
                size = int(self.headers.get('Content-Length','0'))
                if not 0 < size <= 24000:
                    return self.send({'error':'Payload must be 1–24000 bytes'},413)
                payload = json.loads(self.rfile.read(size))
                text = payload.get('text','')
                if not isinstance(text,str) or len(text)>12000:
                    raise ValueError('Text must be a string of at most 12000 characters')
                return self.send(infer(model,text))
            except (ValueError, TypeError, AttributeError):
                return self.send({'error':'Enter 5+ English words, at most 12000 characters, as JSON text'},400)

        def log_message(self, *args):
            pass  # Do not log complaint text or search queries.

    print(f'Open http://127.0.0.1:{port} — Ctrl+C to stop',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
