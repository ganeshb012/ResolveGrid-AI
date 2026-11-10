import http.server
import socketserver
import os
import sys

DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), 'dist'))

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        clean_path = self.path.split('?')[0].lstrip('/')
        full_path = os.path.join(DIRECTORY, clean_path)
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            self.path = '/index.html'
        return super().do_GET()

    def log_message(self, format, *args):
        # Silent logging for speed
        pass

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    port = 5173
    server_address = ('127.0.0.1', port)
    httpd = ThreadingHTTPServer(server_address, SPAHandler)
    print(f"SPA Server running on http://127.0.0.1:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

