import json
import socket
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from pathlib import Path

try:
    import socks  # PySocks
except ImportError:
    raise SystemExit("Please install PySocks: pip install pysocks")

PROXY_FILE = Path("proxies/proxy_list.json")
WORKING_FILE = Path("proxies/working_proxies.json")
TARGET_URL = "http://ip-api.com/json/"  # ip-api endpoint (expects IP appended or Host header query)


def _connect_socket(ip: str, port: int, ptype: str, host: str, port_target: int, timeout: float = 8.0):
    """
    Return a connected socket (plain or PySocks) or raise.
    """
    if ptype == "HTTP":
        return socket.create_connection((ip, port), timeout=timeout)
    if ptype in ("SOCKS4", "SOCKS5"):
        sock_type = socks.SOCKS4 if ptype == "SOCKS4" else socks.SOCKS5
        s = socks.socksocket()
        s.set_proxy(sock_type, ip, port)
        s.settimeout(timeout)
        s.connect((host, port_target))
        return s
    raise ValueError(f"Unsupported proxy type: {ptype}")


def _build_request(ptype: str, target_url: str, host: str, path: str) -> bytes:
    """
    Build HTTP request bytes. For HTTP proxies send absolute URL in request line.
    For SOCKS proxies send path (absolute path only).
    """
    request_line = f"GET {target_url if ptype == 'HTTP' else path} HTTP/1.1\r\n"
    headers = (
        f"Host: {host}\r\n"
        f"User-Agent: ProxyTest/1.0\r\n"
        f"Accept: */*\r\n"
        f"Connection: close\r\n\r\n"
    )
    return (request_line + headers).encode("utf-8")


def _parse_http_response(raw: bytes) -> Dict[str, Any]:
    """
    Split raw response into header text and body text. Return dict with header, body.
    """
    parts = raw.split(b"\r\n\r\n", 1)
    headers = parts[0].decode(errors="replace") if parts else ""
    body = parts[1].decode(errors="replace") if len(parts) > 1 else ""
    return {"headers": headers, "body": body}


def _extract_ip_api(body: str) -> Optional[Dict[str, Any]]:
    """
    Try parse ip-api JSON response and normalize the most useful fields.
    Returns None if parse fails or status != success.
    """
    try:
        data = json.loads(body)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Accept both "status":"success" and other forms; if status present and not success => ignore.
    status = data.get("status")
    if status and str(status).lower() != "success":
        return None

    return {
        "status": data.get("status"),
        "query": data.get("query"),
        "country": data.get("country"),
        "countryCode": data.get("countryCode"),
        "region": data.get("region"),
        "regionName": data.get("regionName"),
        "city": data.get("city"),
        "zip": data.get("zip"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "timezone": data.get("timezone"),
        "isp": data.get("isp"),
        "org": data.get("org"),
        "as": data.get("as")
    }


def test_proxy(proxy: Dict[str, Any], target_url: str) -> Dict[str, Any]:
    """
    Test a single proxy and return a structured result dict.
    Fields: success, message, response_time, headers, body, ip_api (if available)
    """
    ip = proxy.get("IP Address")
    port = int(proxy.get("Port", 0) or 0)
    ptype = (proxy.get("Type") or "HTTP").upper()

    parsed = urlparse(target_url)
    host = parsed.hostname
    port_target = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    start = time.time()
    try:
        sock = _connect_socket(ip, port, ptype, host, port_target)
        req = _build_request(ptype, target_url, host, path)
        sock.sendall(req)

        raw = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            raw += chunk
        sock.close()
        elapsed = time.time() - start

        parsed_resp = _parse_http_response(raw)
        headers = parsed_resp["headers"]
        body = parsed_resp["body"]

        # Preview print (keeps your example CLI output)
        print("\n--- Response Headers ---")
        print(headers)
        print("\n--- Response Body (first 300 chars) ---")
        print(body[:300])
        print("-------------------------\n")

        success = headers.splitlines()[0].upper().find("200 OK") != -1
        message = "Success" if success else f"Bad status: {headers.splitlines()[0] if headers else 'no headers'}"

        ip_api = _extract_ip_api(body) if body else None

        return {
            "success": success,
            "message": message,
            "response_time": round(elapsed, 3),
            "headers": headers,
            "body": body,
            "ip_api": ip_api,
        }

    except Exception as exc:
        elapsed = time.time() - start
        return {
            "success": False,
            "message": str(exc),
            "response_time": round(elapsed, 3),
            "headers": "",
            "body": "",
            "ip_api": None,
        }


def main() -> None:
    if not PROXY_FILE.exists():
        raise FileNotFoundError(f"{PROXY_FILE} not found.")

    with PROXY_FILE.open("r", encoding="utf-8") as fh:
        proxies = json.load(fh)

    working = []
    for proxy in proxies:
        ip = proxy.get("IP Address")
        port = proxy.get("Port")
        ptype = proxy.get("Type")
        print(f"Testing {ip}:{port} ({ptype})... ", end="", flush=True)

        result = test_proxy(proxy, TARGET_URL)
        if result["success"]:
            print("✅ Working")
            record = proxy.copy()
            # Core probe metrics
            record.update({
                "response_time": result["response_time"],
                "probe_message": result["message"],
                "headers": result["headers"],
                "body_preview": result["body"][:200],  # keep JSON readable in file
            })
            # Add parsed ip-api object if available
            if result.get("ip_api"):
                record["ip_api"] = result["ip_api"]
                # For convenience, copy high-value fields to top-level
                record.update({
                    "country": result["ip_api"].get("country"),
                    "countryCode": result["ip_api"].get("countryCode"),
                    "region": result["ip_api"].get("region"),
                    "regionName": result["ip_api"].get("regionName"),
                    "city": result["ip_api"].get("city"),
                    "zip": result["ip_api"].get("zip"),
                    "lat": result["ip_api"].get("lat"),
                    "lon": result["ip_api"].get("lon"),
                    "timezone": result["ip_api"].get("timezone"),
                    "isp": result["ip_api"].get("isp"),
                    "org": result["ip_api"].get("org"),
                    "asn": result["ip_api"].get("as"),
                    "query": result["ip_api"].get("query"),
                })
            working.append(record)
        else:
            print(f"❌ Failed ({result['message']})")

    # Persist results
    with WORKING_FILE.open("w", encoding="utf-8") as fh:
        json.dump(working, fh, indent=4, ensure_ascii=False)

    print(f"\nSaved {len(working)} working proxies -> {WORKING_FILE}")


if __name__ == "__main__":
    main()
