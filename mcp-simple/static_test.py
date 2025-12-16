"""
Simple HTTP server to test ingress routing
"""
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        elif self.path == '/sse':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = b'<html><body><h1>SSE endpoint found!</h1><p>Ingress routing to /sse works</p></body></html>'
            self.wfile.write(html)
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = b'<html><body><h1>Ingress Test Server</h1><p>Path: ' + self.path.encode() + b'</p></body></html>'
            self.wfile.write(html)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), SimpleHandler)
    print('Static test server running on 0.0.0.0:8080')
    server.serve_forever()
