"""
AnonyNet Proxy Server
Author: MD. SABBIR HOSHEN HOOWLADER
Website: https://sabbir28.github.io/
License: MIT License
Description: AnonyNet is a proxy server designed to anonymize user requests by 
             routing them through random public proxies. It aims to enhance 
             privacy and security while browsing by masking the user's IP address.
"""

import socket
import threading
import select
import signal
import sys


class AnonyNetProxyServer:
    """
    A proxy server that handles HTTP and HTTPS requests by forwarding them
    to the target web servers.
    
    Attributes:
        listening_addr (str): The address on which the proxy server listens
        listening_port (int): The port on which the proxy server listens
        buffer_size (int): Maximum amount of data to be sent/received in one go
        server_socket (socket): The main server socket
        client_threads (list): List to keep track of all client threads
        running (bool): Flag indicating if the server is running
    """
    
    def __init__(self, listening_addr='0.0.0.0', listening_port=8888, buffer_size=5242880):
        """
        Initialize the AnonyNet proxy server.
        
        Args:
            listening_addr (str): The address to listen on (default: '0.0.0.0')
            listening_port (int): The port to listen on (default: 8888)
            buffer_size (int): Buffer size for data transfer (default: 5MB)
        """
        self.listening_addr = listening_addr
        self.listening_port = listening_port
        self.buffer_size = buffer_size
        self.server_socket = None
        self.client_threads = []
        self.running = False
        
    def handle_client(self, client_socket):
        """
        Handle client requests and route them to the appropriate web server.
        
        Args:
            client_socket (socket): The socket connected to the client
        """
        try:
            request = client_socket.recv(self.buffer_size)
            
            if not request:
                client_socket.close()
                return
                
            first_line = request.split(b'\n')[0]
            url = first_line.split(b' ')[1]

            http_pos = url.find(b"://")
            if http_pos == -1:
                temp = url
            else:
                temp = url[(http_pos + 3):]

            port_pos = temp.find(b":")
            webserver_pos = temp.find(b"/")
            if webserver_pos == -1:
                webserver_pos = len(temp)

            webserver = ""
            port = -1
            if port_pos == -1 or webserver_pos < port_pos:
                port = 80 if first_line.startswith(b"GET http") else 443
                webserver = temp[:webserver_pos]
            else:
                port = int((temp[(port_pos + 1):])[:webserver_pos - port_pos - 1])
                webserver = temp[:port_pos]

            if first_line.startswith(b"CONNECT"):
                self.handle_https(client_socket, webserver, port)
            else:
                self.handle_http(client_socket, request, webserver, port)
                
        except Exception as e:
            print(f"Error in handle_client: {e}")
            client_socket.close()

    def handle_http(self, client_socket, request, webserver, port):
        """
        Handle HTTP requests and forward them to the target web server.
        
        Args:
            client_socket (socket): The socket connected to the client
            request (bytes): The HTTP request received from the client
            webserver (str): The target web server to forward to
            port (int): The port on the target web server
        """
        proxy_socket = None
        try:
            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.settimeout(30)
            proxy_socket.connect((webserver, port))
            proxy_socket.send(request)

            while True:
                data = proxy_socket.recv(self.buffer_size)
                if len(data) > 0:
                    client_socket.send(data)
                else:
                    break
                    
        except Exception as e:
            print(f"Error handling HTTP request: {e}")
        finally:
            if proxy_socket:
                proxy_socket.close()
            client_socket.close()

    def handle_https(self, client_socket, webserver, port):
        """
        Handle HTTPS connections by tunneling data between client and web server.
        
        Args:
            client_socket (socket): The socket connected to the client
            webserver (str): The target web server to forward to
            port (int): The port on the target web server
        """
        proxy_socket = None
        try:
            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.settimeout(30)
            proxy_socket.connect((webserver, port))
            client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")

            sockets = [client_socket, proxy_socket]
            while True:
                read_sockets, _, error_sockets = select.select(sockets, [], sockets, 30)
                if error_sockets:
                    break
                    
                if not read_sockets:
                    break
                    
                for sock in read_sockets:
                    other_sock = proxy_socket if sock == client_socket else client_socket
                    try:
                        data = sock.recv(self.buffer_size)
                        if data:
                            other_sock.send(data)
                        else:
                            break
                    except socket.error:
                        break
                        
        except Exception as e:
            print(f"Error handling HTTPS request: {e}")
        finally:
            if proxy_socket:
                proxy_socket.close()
            client_socket.close()

    def signal_handler(self, sig, frame):
        """
        Handle shutdown signals and gracefully shut down the server.
        
        Args:
            sig (int): Signal number
            frame: Current stack frame
        """
        print("Shutting down the server...")
        self.stop()

    def start(self):
        """
        Start the proxy server and begin listening for connections.
        """
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.listening_addr, self.listening_port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1)
            
            self.running = True
            
            signal.signal(signal.SIGINT, self.signal_handler)
            
            print(f"AnonyNet Proxy Server started on {self.listening_addr}:{self.listening_port}")
            print("Press Ctrl+C to stop the server")

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    print(f"Accepted connection from {addr[0]}:{addr[1]}")

                    client_handler = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket,),
                        daemon=True
                    )
                    client_handler.start()
                    self.client_threads.append(client_handler)
                    
                    # Clean up finished threads
                    self.client_threads = [t for t in self.client_threads if t.is_alive()]
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"Socket error: {e}")
                except Exception as e:
                    if self.running:
                        print(f"Error accepting connections: {e}")
                        
        except Exception as e:
            print(f"Failed to start server: {e}")
        finally:
            self.cleanup()

    def stop(self):
        """
        Stop the proxy server gracefully.
        """
        self.running = False
        self.cleanup()

    def cleanup(self):
        """
        Clean up resources and close sockets.
        """
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None


def main():
    """
    Main function to run the AnonyNet proxy server.
    """
    proxy_server = AnonyNetProxyServer()
    proxy_server.start()


if __name__ == "__main__":
    main()