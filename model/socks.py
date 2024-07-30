import csv
import socket
import socks
import http.client

def setup_socks_proxy(proxy_url):
    proxy_parts = proxy_url.split('://')
    scheme = proxy_parts[0]
    host, port = proxy_parts[1].split(':')
    port = int(port)

    if scheme == 'socks4':
        socks.set_default_proxy(socks.SOCKS4, host, port)
    elif scheme == 'socks5':
        socks.set_default_proxy(socks.SOCKS5, host, port)
    else:
        raise ValueError(f"Unsupported SOCKS scheme: {scheme}")

    # Patch socket with SOCKS proxy
    socket.socket = socks.socksocket

def send_requests_with_proxies(csv_file_path, url):
    responses = []

    with open(csv_file_path, mode='r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header

        proxies_list = [row[0] for row in reader]

    parsed_url = http.client.urlsplit(url)
    host = parsed_url.hostname
    port = parsed_url.port or (80 if parsed_url.scheme == 'http' else 443)
    path = parsed_url.path or '/'
    scheme = parsed_url.scheme

    for proxy in proxies_list:
        try:
            if proxy.startswith('socks4://') or proxy.startswith('socks5://'):
                setup_socks_proxy(proxy)
                conn = http.client.HTTPConnection(host, port)
            else:
                conn = http.client.HTTPConnection(host, port)
                
            conn.request('GET', path)
            response = conn.getresponse()
            content = response.read().decode()

            responses.append((proxy, response.status, content))
            break  # Stop trying more proxies if the request succeeds
        except Exception as e:
            responses.append((proxy, None, str(e)))
            continue  # Try the next proxy if the current one fails

    return responses

# Example usage:
csv_file_path = 'proxies/db/working_proxies.csv'
url = 'http://example.com'
responses = send_requests_with_proxies(csv_file_path, url)

for proxy, status, content in responses:
    print(f"Proxy: {proxy}, Status: {status}, Content: {content[:100]}")  # Print the first 100 characters of the content
