# AnonyNet Proxy Server
# Author: MD. SABBIR HOSHEN HOOWLADER
# Website: https://sabbir28.github.io/
# License: MIT License
# Description: AnonyNet is a proxy server designed to anonymize user requests by routing them through random public proxies. 
# It aims to enhance privacy and security while browsing by masking the user's IP address and encrypting data.

import socket
import threading
import select
import signal
import sys

# Configuration
LISTENING_ADDR = '0.0.0.0'  # The address on which the proxy server listens
LISTENING_PORT = 8888  # The port on which the proxy server listens
BUFFER_SIZE = 5242880  # Maximum amount of data to be sent/received in one go (5 MB)

# Global variables
server_socket = None  # The main server socket
client_threads = []  # List to keep track of all client threads

def handle_client(client_socket):
    """
    Handles client requests and routes them to the appropriate web server.

    Parameters:
    -----------
    client_socket : socket
        The socket connected to the client.
    """
    try:
        # Receive the client's request
        request = client_socket.recv(BUFFER_SIZE)

        # Parse the request to extract the target address and port
        first_line = request.split(b'\n')[0]  # Get the first line of the request (e.g., GET http://example.com)
        url = first_line.split(b' ')[1]  # Extract the URL from the first line

        # Check if the request is for the secret /info path
        if url == b"/info":
            send_server_info(client_socket)
            return

        # Determine whether the URL includes the protocol (http:// or https://)
        http_pos = url.find(b"://")  
        if http_pos == -1:
            temp = url  # No protocol specified
        else:
            temp = url[(http_pos + 3):]  # Strip off the protocol part

        # Find the port (if any) and the position of the web server name
        port_pos = temp.find(b":")
        webserver_pos = temp.find(b"/")
        if webserver_pos == -1:
            webserver_pos = len(temp)

        # Determine the web server and port to connect to
        webserver = ""
        port = -1
        if port_pos == -1 or webserver_pos < port_pos:
            # Default to port 80 for HTTP or 443 for HTTPS if no port is specified
            port = 80 if first_line.startswith(b"GET http") else 443
            webserver = temp[:webserver_pos]
        else:
            # Extract the port and web server name
            port = int((temp[(port_pos + 1):])[:webserver_pos - port_pos - 1])
            webserver = temp[:port_pos]

        # Handle HTTPS connections separately from HTTP
        if first_line.startswith(b"CONNECT"):
            handle_https(client_socket, webserver, port)
        else:
            handle_http(client_socket, request, webserver, port)
    except Exception as e:
        print(f"Error in handle_client: {e}")
    finally:
        # Close the client socket after handling the request
        client_socket.close()

def send_server_info(client_socket):
    """
    Sends server details in response to requests for /info.

    Parameters:
    -----------
    client_socket : socket
        The socket connected to the client.
    """
    try:
        # Define the server details to be displayed
        info = (
            "AnonyNet Proxy Server\n"
            "----------------------\n"
            "Author: MD. SABBIR HOSHEN HOOWLADER\n"
            "Website: https://sabbir28.github.io/\n"
            "License: MIT License\n"
            "Description: AnonyNet anonymizes user requests by routing them through random public proxies.\n"
            "Server Name: AnonyNet\n"
            "Functionalities: HTTP/HTTPS proxy, Anonymization, Traffic Routing\n"
            "More Projects: Visit https://github.com/sabbir28/AnonyNet for more details.\n"
        )

        # Prepare the HTTP response
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: " + str(len(info)).encode() + b"\r\n"
            b"\r\n" +
            info.encode()
        )

        # Send the response to the client
        client_socket.send(response)
    except Exception as e:
        print(f"Error sending server info: {e}")

def handle_http(client_socket, request, webserver, port):
    """
    Handles HTTP requests and forwards them to the target web server.

    Parameters:
    -----------
    client_socket : socket
        The socket connected to the client.
    request : bytes
        The HTTP request received from the client.
    webserver : str
        The target web server to which the request is forwarded.
    port : int
        The port on the target web server.
    """
    try:
        # Create a socket to connect to the web server
        proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_socket.connect((webserver, port))

        # Send the HTTP request to the web server
        proxy_socket.send(request)

        # Continuously read data from the web server and send it back to the client
        while True:
            data = proxy_socket.recv(BUFFER_SIZE)
            if len(data) > 0:
                client_socket.send(data)  # Send the response data to the client
            else:
                break  # No more data from the web server
    except Exception as e:
        print(f"Error handling HTTP request: {e}")
    finally:
        # Close both sockets after handling the request
        proxy_socket.close()
        client_socket.close()

def handle_https(client_socket, webserver, port):
    """
    Handles HTTPS connections by tunneling data between the client and the web server.

    Parameters:
    -----------
    client_socket : socket
        The socket connected to the client.
    webserver : str
        The target web server to which the request is forwarded.
    port : int
        The port on the target web server.
    """
    try:
        # Create a socket to connect to the web server
        proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_socket.connect((webserver, port))

        # Send a 200 OK response to the client, indicating that the connection is established
        client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        # Add the client and proxy sockets to the list of readable connections
        sockets = [client_socket, proxy_socket]
        while True:
            # Wait for data to be available on either socket
            read_sockets, _, error_sockets = select.select(sockets, [], sockets)
            if error_sockets:
                break  # Exit if there is an error with any socket
            for sock in read_sockets:
                other_sock = proxy_socket if sock == client_socket else client_socket
                data = sock.recv(BUFFER_SIZE)
                if data:
                    other_sock.send(data)  # Send data to the other socket
                else:
                    break  # Exit if no data is received
    except Exception as e:
        print(f"Error handling HTTPS request: {e}")
    finally:
        # Close both sockets after handling the request
        proxy_socket.close()
        client_socket.close()

def start_server():
    """
    Starts the proxy server and listens for incoming client connections.
    """
    global server_socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((LISTENING_ADDR, LISTENING_PORT))
    server_socket.listen(5)  # Listen for up to 5 pending connections

    print(f"[*] Listening on {LISTENING_ADDR}:{LISTENING_PORT}")

    while True:
        try:
            # Accept an incoming client connection
            client_socket, addr = server_socket.accept()
            print(f"[*] Accepted connection from {addr[0]}:{addr[1]}")

            # Handle the client connection in a new thread
            client_handler = threading.Thread(target=handle_client, args=(client_socket,))
            client_handler.start()
            client_threads.append(client_handler)
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"Error accepting connections: {e}")
            break

def signal_handler(sig, frame):
    """
    Handles shutdown signals (e.g., Ctrl+C) and gracefully shuts down the server.

    Parameters:
    -----------
    sig : int
        Signal number.
    frame : FrameType
        Current stack frame.
    """
    print("\n[!] Shutting down the server...")
    if server_socket:
        server_socket.close()  # Close the server socket
    for t in client_threads:
        t.join()  # Wait for all client threads to finish
    sys.exit(0)  # Exit the program

if __name__ == "__main__":
    # Set up signal handling to gracefully shut down the server on SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    start_server()
