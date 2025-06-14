# Make sure to install rich: pip install rich

import statistics
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box
import socket
import threading
import argparse
import sys
import signal
import time
import queue
import requests

# ========== Global Stats ==========
BUFFER_SIZE = 8192
shutdown_flag = threading.Event()
all_connections = []
all_threads = []
start_time = time.time()

total_connections = 0
active_connections = 0
traffic_sent = 0
traffic_received = 0
connection_logs = queue.deque(maxlen=10)

try:
    public_ip = requests.get("https://api.ipify.org", timeout=5).text
except requests.RequestException:
    public_ip = "127.0.0.1"

try:
    if public_ip != "127.0.0.1":
        ip_info = requests.get(f"https://ipinfo.io/{public_ip}/json", timeout=5).json()
        country = ip_info.get("country", "Unknown")
        isp = ip_info.get("org", "Unknown ISP")
    else:
        country = "Localhost"
        isp = "Localhost ISP"
except requests.RequestException:
    country = "Unknown"
    isp = "Unknown ISP"
response_times = queue.deque(maxlen=1000)  # stores last 1000 response times in ms


# ========== DNS Resolver ==========

def resolve_hostname(hostname):
    dns_servers = ["8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1"]  # Google DNS and Cloudflare DNS
    for dns_server in dns_servers:
        try:
            resolver = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP, family=socket.AF_INET)
            for result in resolver:
                ip = result[4][0]
                Log.info(f"Resolved {hostname} to {ip} using DNS server {dns_server}")
                return ip
        except socket.gaierror as e:
            Log.warn(f"Failed to resolve {hostname} using DNS server {dns_server}: {e}")
    Log.error(f"DNS resolution failed for {hostname} after trying all servers")
    return None


# ========== Logging ==========

class Log:
    @staticmethod
    def info(msg): connection_logs.append(("INFO", msg))
    @staticmethod
    def warn(msg): connection_logs.append(("WARN", msg))
    @staticmethod
    def error(msg): connection_logs.append(("ERROR", msg))
    @staticmethod
    def http(msg): connection_logs.append(("HTTP", msg))
    @staticmethod
    def https(msg): connection_logs.append(("HTTPS", msg))

def format_bytes(num):
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{num:.2f} PB"

def build_dashboard():
    elapsed = int(time.time() - start_time)

    # Status Panel
    status_panel = Panel(
        f"[bold green]🟢 Running[/bold green]\n"
        f"[bold]Uptime:[/bold] {elapsed} sec\n"
        f"[bold]Active Connections:[/bold] {active_connections}\n"
        f"[bold]Total Connections:[/bold] {total_connections}",
        title="🌐 [bold cyan]Status[/bold cyan]",
        border_style="green",
        padding=(1, 2),
    )

    # Response Times Panel
    if response_times:
        avg_resp = f"{statistics.mean(response_times):.2f} ms"
        min_resp = f"{min(response_times):.2f} ms"
        max_resp = f"{max(response_times):.2f} ms"
    else:
        avg_resp = min_resp = max_resp = "N/A"

    response_panel = Panel(
        f"[bold]📈 Avg Response:[/bold] {avg_resp}\n"
        f"[bold]📉 Min Response:[/bold] {min_resp}\n"
        f"[bold]📈 Max Response:[/bold] {max_resp}",
        title="⏱️ [bold magenta]Response Times[/bold magenta]",
        border_style="magenta",
        padding=(1, 2),
    )

    # Server Info Panel
    server_info = Panel(
        f"[bold]IP:[/bold] {public_ip}\n"
        f"[bold]Country:[/bold] {country}\n"
        f"[bold]ISP:[/bold] {isp}",
        title="🖥️ [bold yellow]Server Info[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    )

    # Traffic Panel
    traffic_panel = Panel(
        f"[bold]↑ Sent:[/bold] {format_bytes(traffic_sent)}\n"
        f"[bold]↓ Received:[/bold] {format_bytes(traffic_received)}",
        title="📊 [bold blue]Traffic[/bold blue]",
        border_style="blue",
        padding=(1, 2),
    )

    # Logs Table
    log_table = Table(title="🧾 [bold red]Recent Logs[/bold red]", expand=True, box=box.SIMPLE)
    log_table.add_column("Level", style="bold cyan", justify="center")
    log_table.add_column("Message", style="dim white", justify="left")
    for level, msg in list(connection_logs)[-10:]:
        log_table.add_row(f"[{level.lower()}]{level}[/]", msg)

    # Dashboard Layout
    grid = Table.grid(expand=True)
    grid.add_row(status_panel, traffic_panel)
    grid.add_row(server_info, response_panel)
    grid.add_row(log_table)

    return grid

# ========== Forwarding ==========

def forward(src, dst, count_sent=True):
    global traffic_sent, traffic_received
    try:
        while not shutdown_flag.is_set():
            data = src.recv(BUFFER_SIZE)
            if not data:
                break
            dst.sendall(data)
            if count_sent:
                traffic_sent += len(data)
            else:
                traffic_received += len(data)
    except Exception as e:
        Log.warn(f"Forward error: {e}")
    finally:
        src.close()
        dst.close()

# ========== Client Handler ==========

def handle_client(client_socket, client_address):
    global active_connections, total_connections
    active_connections += 1
    total_connections += 1

    try:
        request = client_socket.recv(BUFFER_SIZE).decode('utf-8', errors='ignore')
        if not request:
            return client_socket.close()

        first_line = request.split('\n')[0]

        if request.startswith("CONNECT"):
            host_port = first_line.split()[1]
            host, port = host_port.split(":")
            port = int(port)

            reason, is_blocked = is_domain_blocked(host)
            if is_blocked:
                Log.warn(f"Blocked HTTPS {host}:{port} - Reason: {reason}")
                client_socket.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 14\r\n\r\nBlocked Domain")
                return client_socket.close()

            Log.https(f"{client_address[0]}:{client_address[1]} CONNECT {host}:{port}")
            try:
                start = time.perf_counter()
                remote = socket.create_connection((host, port))
                end = time.perf_counter()
                response_times.append((end - start) * 1000)

                client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                threading.Thread(target=forward, args=(client_socket, remote, True), daemon=True).start()
                threading.Thread(target=forward, args=(remote, client_socket, False), daemon=True).start()
            except Exception as e:
                Log.error(f"{client_address[0]} HTTPS Error: {e}")
                client_socket.close()

        else:
            method, path, _ = first_line.split()
            host = ''
            for line in request.split('\n'):
                if line.lower().startswith("host:"):
                    host = line.split(":", 1)[1].strip()
                    break

            if method == "GET" and path.strip() == "/":
                client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK")
                return

            if not host:
                Log.warn(f"{client_address[0]} No Host header")
                return client_socket.close()

            reason, is_blocked = is_domain_blocked(host)
            if is_blocked:
                Log.warn(f"Blocked HTTP {host}{path} - Reason: {reason}")
                client_socket.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: 14\r\n\r\nBlocked Domain")
                return client_socket.close()

            Log.http(f"{client_address[0]} {method} http://{host}{path}")

            start = time.perf_counter()
            remote = socket.create_connection((host, 80))
            end = time.perf_counter()
            response_times.append((end - start) * 1000)

            remote.sendall(request.encode())

            threading.Thread(target=forward, args=(client_socket, remote, True), daemon=True).start()
            threading.Thread(target=forward, args=(remote, client_socket, False), daemon=True).start()

    except Exception as e:
        Log.error(f"{client_address[0]} Handler error: {e}")
    finally:
        active_connections -= 1


# ========== Server ==========

def start_proxy(host='0.0.0.0', port=8000):
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(100)
    except Exception as e:
        Log.error(f"Failed to start server on {host}:{port}: {e}")
        sys.exit(1)

    def shutdown(signum=None, frame=None):
        Log.warn("Shutting down server...")
        shutdown_flag.set()
        try: server.close()
        except: pass
        for conn in all_connections:
            try: conn.close()
            except: pass
        for t in all_threads:
            t.join(timeout=1)
        Log.info("Goodbye 👋")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    with Live(build_dashboard(), refresh_per_second=1, screen=True) as live:
        while not shutdown_flag.is_set():
            try:
                client_sock, addr = server.accept()
                all_connections.append(client_sock)
                Log.info(f"New connection from {addr}")
                t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
                t.start()
                all_threads.append(t)
                live.update(build_dashboard())
            except Exception as e:
                Log.error(f"Server error: {e}")
                shutdown()

# ========== CLI ==========
def main():
    parser = argparse.ArgumentParser(description="Live CLI Proxy Server")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Port to listen")
    parser.add_argument("-w", "--webui", action='store_true', help="Enable Web UI")
    args = parser.parse_args()

    if args.webui:
        Log.info("Web UI enabled. Starting web server...")
        
        # Creat an instance of WebUI to start the web server
        # also creat a thread to run the web UI server
        web_ui = WebUI(host=args.host, port=8080)
        web_ui_thread = threading.Thread(target=web_ui.start_server, daemon=True)
        web_ui_thread.start()
        Log.info(f"Starting proxy server on {args.host}:{args.port}")


    # Start the proxy server
    start_proxy(args.host, args.port)

# ========== WEB UI ==========
class WebUI:
    def __init__(self, host='0.0.0.0', port=8080):
        self.ip = public_ip
        self.country = country
        self.isp = isp
        self.start_time = start_time
        self.total_connections = total_connections
        self.active_connections = active_connections
        self.traffic_sent = traffic_sent
        self.traffic_received = traffic_received
        self.host = host
        self.port = port

    def get_stats(self):
        elapsed = int(time.time() - self.start_time)
        return {
            "ip": self.ip,
            "country": self.country,
            "isp": self.isp,
            "elapsed": elapsed,
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "traffic_sent": format_bytes(self.traffic_sent),
            "traffic_received": format_bytes(self.traffic_received),
            "response_times": list(response_times)
        }

    def start_server(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            Log.info(f"Web UI running on http://{self.host}:{self.port}")
        except Exception as e:
            Log.error(f"Failed to start Web UI server: {e}")
            return

        while not shutdown_flag.is_set():
            try:
                client_socket, client_address = server_socket.accept()
                request = client_socket.recv(BUFFER_SIZE).decode('utf-8', errors='ignore')
                if not request:
                    client_socket.close()
                    continue

                # Simple JSON response
                if request.startswith("GET"):
                    stats = self.get_stats()
                    response_body = (
                        "{"
                        f"\"ip\": \"{stats['ip']}\","
                        f"\"country\": \"{stats['country']}\","
                        f"\"isp\": \"{stats['isp']}\","
                        f"\"uptime\": {stats['elapsed']},"
                        f"\"total_connections\": {stats['total_connections']},"
                        f"\"active_connections\": {stats['active_connections']},"
                        f"\"traffic_sent\": \"{stats['traffic_sent']}\","
                        f"\"traffic_received\": \"{stats['traffic_received']}\","
                        f"\"response_times\": {stats['response_times']}"
                        "}"
                    )
                    response = (
                        "HTTP/3 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(response_body)}\r\n"
                        "Connection: close\r\n\r\n"
                        + response_body
                    )
                    client_socket.sendall(response.encode('utf-8'))
                client_socket.close()
            except Exception as e:
                Log.error(f"Web UI error: {e}")
                client_socket.close()
        

# ========== Blocked Domains ==========

def is_domain_blocked(domain: str) -> tuple[bool, str]:
    """
    Checks if a given domain should be blocked based on predefined lists
    of tracking and advertising domains.

    Args:
        domain (str): The domain to check (e.g., "www.google-analytics.com").

    Returns:
        tuple[bool, str]: A tuple where:
            - The first element (bool) is True if the domain is blocked, False otherwise.
            - The second element (str) is a message indicating why it's blocked
              or "Not Blocked" if it's not on any blocklist.
    """

    # Normalize the domain to lower case for case-insensitive matching
    domain = domain.lower()

    # --- Blocklist Categories ---

    # 1. Major Ad Networks & Advertising Platforms
    ad_networks = {
        "doubleclick.net": "Google AdSense/DoubleClick",
        "googlesyndication.com": "Google AdSense/DoubleClick",
        "adservice.google.com": "Google AdSense/DoubleClick",
        "googleads.g.doubleclick.net": "Google AdSense/DoubleClick",
        "facebook.com/tr": "Facebook Pixel/Tracking (partial URL, proxy should handle)",
        "fbcdn.net": "Facebook CDN (often related to ads/tracking)",
        "amazon-adsystem.com": "Amazon Advertising",
        "adnxs.com": "AppNexus (Xandr) Advertising",
        "ad.com": "AOL Advertising",
        "adsrvr.org": "The Trade Desk (Ad Platform)",
        "criteo.com": "Criteo Retargeting Ads",
        "openx.net": "OpenX Ad Exchange",
        "rubiconproject.com": "Magnite (formerly Rubicon Project) Ad Exchange",
        "appnexus.com": "AppNexus (Xandr) Advertising",
        "zedo.com": "Zedo Ad Network",
        "servedby.flashtalking.com": "Flashtalking Ad Serving",
        "pixel.facebook.com": "Facebook Pixel",
        "addthis.com": "AddThis Social Sharing/Tracking",
        "sharethis.com": "ShareThis Social Sharing/Tracking",
        "outbrain.com": "Outbrain Native Advertising",
        "taboola.com": "Taboola Native Advertising",
    }

    # 2. Analytics & User Tracking Services
    analytics_trackers = {
        "google-analytics.com": "Google Analytics",
        "googletagmanager.com": "Google Tag Manager (often used for analytics/tracking)",
        "mixpanel.com": "Mixpanel Analytics",
        "segment.com": "Segment Data Platform",
        "hotjar.com": "Hotjar User Behavior Analytics",
        "scorecardresearch.com": "Comscore Digital Measurement",
        "telemetry.microsoft.com": "Microsoft Telemetry/Data Collection",
        "vortex.data.microsoft.com": "Microsoft Telemetry/Data Collection",
        "log.mixpanel.com": "Mixpanel Event Logging",
        "piwik.pro": "Piwik PRO Analytics Suite",
        # "matomo.org": "Matomo Analytics (Often self-hosted, block if public instance is known to track)",
        "amplitude.com": "Amplitude Product Analytics",
        "heap.io": "Heap Analytics",
    }

    # 3. Social Media Trackers (Beyond main platform domains)
    social_trackers = {
        "platform.twitter.com": "Twitter Widgets/Tracking",
        "connect.facebook.net": "Facebook Connect (Login/Social Plugins)",
        "t.co": "Twitter URL Shortener/Tracker",
        "disqus.com": "Disqus Comments (can include tracking)",
    }

    # 4. Content Delivery Networks (CDNs) often used for ads/trackers
    #    Be cautious when blocking CDNs, as it can break legitimate content.
    #    Only block specific subdomains known for malicious use.
    cdn_trackers = {
        "s0.2mdn.net": "DoubleClick CDN (often for ad assets)",
        "sentry-cdn.com": "Sentry Error Tracking/Telemetry CDN",
        # Add more specific CDN subdomains if you identify them as problematic
    }

    # 5. Known Malware/Malvertising Domains (Example, actual list would be huge)
    malicious_domains = {
        "coin-hive.com": "In-browser Cryptominer",
        # This category would ideally be populated from large, regularly updated blacklists
    }

    # --- Check against blocklists ---

    # Helper function to check if domain or any subdomain is in a list
    def check_and_get_reason(domain_to_check, blocklist_dict):
        # Check for exact match
        if domain_to_check in blocklist_dict:
            return True, blocklist_dict[domain_to_check]
        
        # Check for subdomains (e.g., if blocking "example.com", also block "sub.example.com")
        # This is a common pattern for ad/tracking networks
        parts = domain_to_check.split('.')
        for i in range(len(parts)):
            sub_domain_candidate = ".".join(parts[i:])
            if sub_domain_candidate in blocklist_dict:
                return True, blocklist_dict[sub_domain_candidate]
        return False, "Not Blocked"

    # Check against each category
    is_blocked, reason = check_and_get_reason(domain, ad_networks)
    if is_blocked:
        return True, f"Ad Network: {reason}"

    is_blocked, reason = check_and_get_reason(domain, analytics_trackers)
    if is_blocked:
        return True, f"Analytics/Tracking: {reason}"

    is_blocked, reason = check_and_get_reason(domain, social_trackers)
    if is_blocked:
        return True, f"Social Media Tracker: {reason}"

    is_blocked, reason = check_and_get_reason(domain, cdn_trackers)
    if is_blocked:
        return True, f"CDN-based Tracker: {reason}"
    
    is_blocked, reason = check_and_get_reason(domain, malicious_domains)
    if is_blocked:
        return True, f"Malicious/Cryptominer: {reason}"

    # If no match found
    return False, "Not Blocked"


if __name__ == '__main__':
    main()
