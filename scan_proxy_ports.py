#!/usr/bin/env python3
import socket
import threading
import ipaddress
from queue import Queue
import time

PORT = 8000
TIMEOUT = 1.0
MAX_THREADS = 200
CUSTOM_RANGES = []

ip_queue = Queue()
open_ips = []

def log(msg, tag="INFO"):
    ts = time.strftime('%H:%M:%S')
    print(f"[{tag}] {ts} - {msg}")

def is_proxy_alive(ip):
    s = None
    try:
        s = socket.create_connection((ip, PORT), timeout=TIMEOUT)
        s.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        response = b""
        while True:
            part = s.recv(1024)
            if not part:
                break
            response += part
            if b"\r\n\r\n" in response:
                break
        text = response.decode(errors='ignore')

        # Original method: check for "200 OK" in headers
        original_check = "200 OK" in text

        # New method: check for "OK" in body
        parts = text.split("\r\n\r\n", 1)
        body = parts[1] if len(parts) > 1 else ""
        new_check = "OK" in body.strip()

        return original_check or new_check

    except Exception:
        return False
    finally:
        if s:
            s.close()

def scan_worker():
    while True:
        ip = ip_queue.get()
        if ip is None:
            ip_queue.task_done()
            break
        try:
            if is_proxy_alive(ip):
                log(f"{ip}:{PORT} is a working proxy!", "✓")
                open_ips.append(ip)
        except Exception:
            pass
        finally:
            ip_queue.task_done()

def scan_range(ip_range):
    try:
        network = ipaddress.ip_network(ip_range, strict=False)
        for ip in network.hosts():
            ip_queue.put(str(ip))
    except ValueError as e:
        log(f"Invalid IP range {ip_range}: {e}", "ERROR")

def get_local_lan_range():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        ip_parts = local_ip.split('.')
        if len(ip_parts) == 4:
            return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        else:
            return None
    except Exception:
        return None
    finally:
        s.close()

def run_scan():
    log("Scanning localhost...", "•")
    ip_queue.put("127.0.0.1")

    lan_range = get_local_lan_range()
    if lan_range:
        log(f"Scanning LAN subnet: {lan_range}", "•")
        scan_range(lan_range)

    for cidr in CUSTOM_RANGES:
        log(f"Scanning custom range: {cidr}", "•")
        scan_range(cidr)

    threads = []
    for _ in range(min(MAX_THREADS, ip_queue.qsize())):
        t = threading.Thread(target=scan_worker, daemon=True)
        t.start()
        threads.append(t)

    ip_queue.join()

    for _ in threads:
        ip_queue.put(None)
    for t in threads:
        t.join()

    log("Scan complete.\n", "✓")
    if open_ips:
        log("Working Proxy IPs:", "+")
        for ip in open_ips:
            print(f"  - {ip}:{PORT}")
    else:
        log("No working proxies found.", "-")

if __name__ == "__main__":
    run_scan()
