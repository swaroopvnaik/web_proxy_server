import http.server
import socketserver
import urllib.request
import urllib.parse
import ssl
import socket
import threading
import select

PORT = 8080

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    timeout = 30
    lock = threading.Lock()

    def do_CONNECT(self):
        """Handle HTTPS CONNECT tunneling"""
        try:
            # Parse the destination address and port
            host, port = self.path.split(':')
            port = int(port)
            
            # Create a connection to the destination
            dest_sock = socket.create_connection((host, port))
            
            # Send 200 Connection established to the client
            self.send_response(200, 'Connection Established')
            self.end_headers()
            
            # Get the client socket
            client_sock = self.connection
            
            # Create SSL context for the destination connection
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            print(f"Established HTTPS tunnel to {host}:{port}")
            
            # Start bidirectional tunneling
            self._tunnel(client_sock, dest_sock)
            
        except Exception as e:
            print(f"CONNECT Error: {e}")
            self.send_error(500, f'CONNECT failed: {str(e)}')
            return

    def _tunnel(self, client_sock, dest_sock):
        """Handle the bidirectional tunneling of data"""
        sockets = [client_sock, dest_sock]
        timeout = 1
        
        while True:
            # Wait until one of the sockets is ready for I/O
            readable, _, exceptional = select.select(sockets, [], sockets, timeout)

            if exceptional:
                break

            for sock in readable:
                other = dest_sock if sock is client_sock else client_sock
                try:
                    data = sock.recv(8192)
                    if not data:
                        return
                    other.sendall(data)
                except (ConnectionResetError, BrokenPipeError, ssl.SSLError) as e:
                    print(f"Tunnel Error: {e}")
                    return

    def do_GET(self):
        """Handle HTTP GET requests"""
        try:
            url = self.path
            print(f"Proxying GET request for: {url}")
            
            # Create headers dictionary from client request
            headers = {key: val for key, val in self.headers.items()}
            headers['Connection'] = 'close'
            
            # Create and send the request
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response:
                # Send the response status code
                self.send_response(response.status)
                
                # Send the response headers
                for key, val in response.headers.items():
                    self.send_header(key, val)
                self.end_headers()
                
                # Send the response body
                self.wfile.write(response.read())
                
        except Exception as e:
            print(f"GET Error: {e}")
            self.send_error(500, f'GET failed: {str(e)}')

    def log_message(self, format, *args):
        """Custom logging with thread identification"""
        thread_id = threading.current_thread().ident
        print(f"[Thread-{thread_id}] {self.client_address[0]}:{self.client_address[1]} - {format % args}")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

def run_proxy_server():
    server_address = ('', PORT)
    httpd = ThreadedHTTPServer(server_address, ProxyHandler)
    print(f"Starting proxy server on port {PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down proxy server...")
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    run_proxy_server()