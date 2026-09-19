#!/usr/bin/env python3
"""
Web Server for StatementFlow Extractor with Anthropic Claude AI Support.
Provides endpoints for AI statement extraction, API key verification, and CSV generation.
"""
import http.server
import socketserver
import os
import json
import urllib.parse
from extractor import parse_statement_pdf, to_csv

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def load_dotenv():
    env_file = os.path.join(DIRECTORY, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v:
                        os.environ[k] = v

load_dotenv()

class StatementHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == '/api/status':
            env_key = os.environ.get('ANTHROPIC_API_KEY')
            has_key = bool(env_key and env_key.strip().startswith('sk-ant-'))
            self._send_json({
                'has_server_key': has_key,
                'default_model': 'claude-haiku-4-5-20251001',
                'models': [
                    {'id': 'claude-haiku-4-5-20251001', 'name': 'Claude Haiku 4.5 (Fast & High Accuracy)'},
                    {'id': 'claude-sonnet-4-5-20250929', 'name': 'Claude Sonnet 4.5 (Advanced Reasoning)'},
                    {'id': 'claude-opus-4-5-20251101', 'name': 'Claude Opus 4.5'}
                ]
            })
        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)

        if parsed_url.path == '/api/test-key':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body) if body else {}
                api_key = data.get('api_key') or self.headers.get('X-Anthropic-Api-Key') or os.environ.get('ANTHROPIC_API_KEY')

                if not api_key or not api_key.strip().startswith('sk-ant-'):
                    self._send_json({'success': False, 'error': 'Invalid key format. Anthropic API keys start with sk-ant-'}, 400)
                    return

                # Test connection using lightweight ping
                import anthropic
                client = anthropic.Anthropic(api_key=api_key.strip())
                test_res = client.messages.create(
                    model='claude-haiku-4-5-20251001',
                    max_tokens=10,
                    messages=[{'role': 'user', 'content': 'hi'}]
                )
                self._send_json({'success': True, 'message': 'Anthropic API key is active and connected successfully!'})
            except Exception as e:
                self._send_json({'success': False, 'error': f'Key verification failed: {str(e)}'}, 400)
            return

        elif parsed_url.path == '/api/parse':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length == 0:
                    self._send_json({'error': 'No file content received'}, 400)
                    return

                # Check for Anthropic API key in header or environment
                api_key = self.headers.get('X-Anthropic-Api-Key') or os.environ.get('ANTHROPIC_API_KEY')
                model = self.headers.get('X-Anthropic-Model') or 'claude-haiku-4-5-20251001'

                body = self.rfile.read(content_length)
                content_type = self.headers.get('Content-Type', '')

                pdf_data = b''
                if 'multipart/form-data' in content_type:
                    boundary = None
                    for part in content_type.split(';'):
                        part = part.strip()
                        if part.startswith('boundary='):
                            boundary = part.split('=', 1)[1].strip('"').encode('latin1')
                            break
                    if boundary:
                        chunks = body.split(b'--' + boundary)
                        for chunk in chunks:
                            if b'filename=' in chunk and b'\r\n\r\n' in chunk:
                                header_part, file_part = chunk.split(b'\r\n\r\n', 1)
                                if file_part.endswith(b'\r\n'):
                                    file_part = file_part[:-2]
                                pdf_data = file_part
                                break
                    if not pdf_data:
                        pdf_data = body
                else:
                    pdf_data = body

                if not pdf_data.startswith(b'%PDF'):
                    pdf_idx = pdf_data.find(b'%PDF')
                    if pdf_idx != -1:
                        pdf_data = pdf_data[pdf_idx:]
                    else:
                        self._send_json({
                            'success': False,
                            'error': 'Uploaded file does not appear to be a valid PDF format.'
                        }, 400)
                        return

                result = parse_statement_pdf(pdf_data, api_key=api_key, model=model)
                transactions = result['transactions']
                validation = result['validation']
                csv_output = to_csv(transactions)

                response_data = {
                    'success': True,
                    'engine': validation.get('engine', 'Unknown'),
                    'count': len(transactions),
                    'overall_confidence': validation.get('overall_confidence', 90),
                    'needs_review_count': validation.get('needs_review_count', 0),
                    'transactions': transactions,
                    'validation': validation,
                    'metadata': result.get('metadata', {}),
                    'csv': csv_output
                }
                self._send_json(response_data)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._send_json({'success': False, 'error': f'Extraction failed: {str(e)}'}, 500)
        else:
            self.send_error(404, "Endpoint not found")

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Anthropic-Api-Key, X-Anthropic-Model, Authorization')

    def _send_json(self, data, status=200):
        response_bytes = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(response_bytes)

def run(port=PORT):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), StatementHandler) as httpd:
        print(f"Statement Extractor Server running at http://localhost:{port}")
        httpd.serve_forever()

if __name__ == '__main__':
    run()
