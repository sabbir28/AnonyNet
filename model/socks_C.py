import csv
import httpx
import socks
import socket

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

    socket.socket = socks.socksocket

def send_requests_with_proxies(csv_file_path, url):
    responses = []

    with open(csv_file_path, mode='r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header

        for row in reader:
            proxy = row[0]

            if proxy.startswith('socks4://') or proxy.startswith('socks5://'):
                setup_socks_proxy(proxy)
                proxies = {
                    'http://': proxy,
                    'https://': proxy
                }
                try:
                    response = httpx.get(url, timeout=10, proxies=proxies)
                    responses.append((proxy, response.status_code, response.text))
                except httpx.RequestError as e:
                    responses.append((proxy, None, str(e)))
            else:
                proxies = {
                    'http://': proxy,
                    'https://': proxy
                }
                try:
                    response = httpx.get(url, timeout=10, proxies=proxies)
                    responses.append((proxy, response.status_code, response.text))
                except httpx.RequestError as e:
                    responses.append((proxy, None, str(e)))
    
    return responses

# Example usage:
csv_file_path = 'proxies/db/working_proxies.csv'
url = 'http://example.com'
responses = send_requests_with_proxies(csv_file_path, url)

for proxy, status, content in responses:
    print(f"Proxy: {proxy}, Status: {status}, Content: {content[:100]}")  # Print the first 100 characters of the content
