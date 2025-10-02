import json
import socket
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
from pathlib import Path
import os

try:
    import socks  # PySocks
except ImportError:
    raise SystemExit("Please install PySocks: pip install pysocks")


class ProxyManager:
    """
    A comprehensive proxy management class that handles proxy scraping, testing, and management.
    
    Attributes:
        proxy_file (Path): Path to store raw proxy list
        working_file (Path): Path to store working proxies
        target_url (str): URL for proxy testing
        headers (Dict): HTTP headers for requests
    """
    
    def __init__(
        self,
        proxy_file: str = "proxies/proxy_list.json",
        working_file: str = "proxies/working_proxies.json",
        target_url: str = "http://ip-api.com/json/",
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the ProxyManager.
        
        Args:
            proxy_file: Path to store raw proxy list
            working_file: Path to store working proxies  
            target_url: URL for proxy testing
            headers: HTTP headers for requests
        """
        self.proxy_file = Path(proxy_file)
        self.working_file = Path(working_file)
        self.target_url = target_url
        
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
        
        # Ensure proxy directories exist
        self.proxy_file.parent.mkdir(parents=True, exist_ok=True)
        self.working_file.parent.mkdir(parents=True, exist_ok=True)

    def fetch_proxy_list(self, url: str = "https://hide.mn/en/proxy-list/") -> Optional[bytes]:
        """
        Fetch proxy list from the specified URL.
        
        Args:
            url: URL to scrape proxies from
            
        Returns:
            bytes: HTML content if successful, None otherwise
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            print(f"✅ Successfully fetched proxy list from {url}")
            return response.content
        except requests.RequestException as e:
            print(f"❌ Failed to retrieve proxy list: {e}")
            return None

    def parse_proxy_list(self, page_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse proxy data from HTML content.
        
        Args:
            page_content: HTML content containing proxy list
            
        Returns:
            List of proxy dictionaries
        """
        soup = BeautifulSoup(page_content, 'html.parser')
        table_block = soup.find('div', class_='table_block')
        
        if not table_block:
            print("❌ Failed to find the proxy table")
            return []
        
        rows = table_block.find('tbody').find_all('tr')
        proxies = []

        for row in rows:
            columns = row.find_all('td')
            if len(columns) >= 7:
                ip_address = columns[0].text.strip()
                port = columns[1].text.strip()
                country = columns[2].find('span', class_='country').text.strip() if columns[2].find('span', class_='country') else ''
                city = columns[2].find('span', class_='city').text.strip() if columns[2].find('span', class_='city') else ''
                speed = columns[3].find('p').text.strip() if columns[3].find('p') else ''
                proxy_type = columns[4].text.strip()
                anonymity = columns[5].text.strip()
                latest_update = columns[6].text.strip()

                proxy_data = {
                    "IP Address": ip_address,
                    "Port": port,
                    "Country": country,
                    "City": city,
                    "Speed": speed,
                    "Type": proxy_type,
                    "Anonymity": anonymity,
                    "Latest Update": latest_update
                }
                proxies.append(proxy_data)
        
        print(f"✅ Parsed {len(proxies)} proxies from HTML")
        return proxies

    def save_proxies_to_json(self, proxies: List[Dict[str, Any]], file_path: Optional[Path] = None) -> bool:
        """
        Save proxy list to JSON file.
        
        Args:
            proxies: List of proxy dictionaries
            file_path: Path to save file (uses self.proxy_file if None)
            
        Returns:
            bool: True if successful
        """
        if file_path is None:
            file_path = self.proxy_file
            
        try:
            with open(file_path, 'w', encoding='utf-8') as json_file:
                json.dump(proxies, json_file, indent=4, ensure_ascii=False)
            print(f"✅ Proxy data saved to {file_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to save proxy data: {e}")
            return False

    def load_proxies_from_json(self, file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Load proxies from JSON file.
        
        Args:
            file_path: Path to load from (uses self.proxy_file if None)
            
        Returns:
            List of proxy dictionaries
        """
        if file_path is None:
            file_path = self.proxy_file
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                proxies = json.load(f)
            print(f"✅ Loaded {len(proxies)} proxies from {file_path}")
            return proxies
        except Exception as e:
            print(f"❌ Failed to load proxies: {e}")
            return []

    def _connect_socket(self, ip: str, port: int, ptype: str, host: str, port_target: int, timeout: float = 8.0) -> socket.socket:
        """
        Create and connect socket through proxy.
        
        Args:
            ip: Proxy IP address
            port: Proxy port
            ptype: Proxy type (HTTP, SOCKS4, SOCKS5)
            host: Target host
            port_target: Target port
            timeout: Connection timeout
            
        Returns:
            Connected socket
            
        Raises:
            ValueError: Unsupported proxy type
            socket.error: Connection failed
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

    def _build_request(self, ptype: str, target_url: str, host: str, path: str) -> bytes:
        """
        Build HTTP request for proxy.
        
        Args:
            ptype: Proxy type
            target_url: Full target URL
            host: Target host
            path: Request path
            
        Returns:
            HTTP request as bytes
        """
        request_line = f"GET {target_url if ptype == 'HTTP' else path} HTTP/1.1\r\n"
        headers = (
            f"Host: {host}\r\n"
            f"User-Agent: ProxyTest/1.0\r\n"
            f"Accept: */*\r\n"
            f"Connection: close\r\n\r\n"
        )
        return (request_line + headers).encode("utf-8")

    def _parse_http_response(self, raw: bytes) -> Dict[str, Any]:
        """
        Parse HTTP response.
        
        Args:
            raw: Raw response bytes
            
        Returns:
            Dict with headers and body
        """
        parts = raw.split(b"\r\n\r\n", 1)
        headers = parts[0].decode(errors="replace") if parts else ""
        body = parts[1].decode(errors="replace") if len(parts) > 1 else ""
        return {"headers": headers, "body": body}

    def _extract_ip_api(self, body: str) -> Optional[Dict[str, Any]]:
        """
        Extract IP information from ip-api response.
        
        Args:
            body: Response body
            
        Returns:
            IP information dict or None
        """
        try:
            data = json.loads(body)
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

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

    def test_proxy(self, proxy: Dict[str, Any], target_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Test a single proxy.
        
        Args:
            proxy: Proxy dictionary
            target_url: URL to test against
            
        Returns:
            Test results dictionary
        """
        if target_url is None:
            target_url = self.target_url
            
        ip = proxy.get("IP Address", "")
        port_str = proxy.get("Port", "0")
        
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": f"Invalid port: {port_str}",
                "response_time": 0.0,
                "headers": "",
                "body": "",
                "ip_api": None,
            }
            
        ptype = (proxy.get("Type") or "HTTP").upper()

        parsed = urlparse(target_url)
        host = parsed.hostname or ""
        port_target = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        start = time.time()
        try:
            sock = self._connect_socket(ip, port, ptype, host, port_target)
            req = self._build_request(ptype, target_url, host, path)
            sock.sendall(req)

            raw = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                raw += chunk
            sock.close()
            elapsed = time.time() - start

            parsed_resp = self._parse_http_response(raw)
            headers = parsed_resp["headers"]
            body = parsed_resp["body"]

            success = headers.splitlines()[0].upper().find("200 OK") != -1
            message = "Success" if success else f"Bad status: {headers.splitlines()[0] if headers else 'no headers'}"

            ip_api = self._extract_ip_api(body) if body else None

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

    def test_all_proxies(self, target_url: Optional[str] = None, max_proxies: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Test all loaded proxies.
        
        Args:
            target_url: URL to test against
            max_proxies: Maximum number of proxies to test
            
        Returns:
            List of working proxies
        """
        if not self.proxy_file.exists():
            print("❌ No proxy file found. Please scrape proxies first.")
            return []

        proxies = self.load_proxies_from_json()
        
        if max_proxies:
            proxies = proxies[:max_proxies]
            
        working = []
        total = len(proxies)
        
        print(f"🧪 Testing {total} proxies...")
        
        for i, proxy in enumerate(proxies, 1):
            ip = proxy.get("IP Address")
            port = proxy.get("Port")
            ptype = proxy.get("Type")
            print(f"[{i}/{total}] Testing {ip}:{port} ({ptype})... ", end="", flush=True)

            result = self.test_proxy(proxy, target_url)
            if result["success"]:
                print("✅ Working")
                record = proxy.copy()
                record.update({
                    "response_time": result["response_time"],
                    "probe_message": result["message"],
                    "headers": result["headers"],
                    "body_preview": result["body"][:200],
                })
                
                if result.get("ip_api"):
                    record["ip_api"] = result["ip_api"]
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

        self.save_proxies_to_json(working, self.working_file)
        print(f"✅ Saved {len(working)} working proxies to {self.working_file}")
        return working

    def scrape_and_save_proxies(self, url: str = "https://hide.mn/en/proxy-list/") -> bool:
        """
        Scrape proxies from URL and save to file.
        
        Args:
            url: URL to scrape from
            
        Returns:
            bool: True if successful
        """
        page_content = self.fetch_proxy_list(url)
        if not page_content:
            return False
            
        proxies = self.parse_proxy_list(page_content)
        if not proxies:
            return False
            
        return self.save_proxies_to_json(proxies)

    def get_working_proxies(self) -> List[Dict[str, Any]]:
        """
        Get list of working proxies.
        
        Returns:
            List of working proxy dictionaries
        """
        return self.load_proxies_from_json(self.working_file)

    def get_fastest_proxies(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the fastest working proxies.
        
        Args:
            count: Number of proxies to return
            
        Returns:
            List of fastest proxies
        """
        working = self.get_working_proxies()
        working.sort(key=lambda x: x.get("response_time", float('inf')))
        return working[:count]

    def get_proxies_by_country(self, country_code: str) -> List[Dict[str, Any]]:
        """
        Get proxies filtered by country code.
        
        Args:
            country_code: Country code to filter by
            
        Returns:
            List of proxies from specified country
        """
        working = self.get_working_proxies()
        return [p for p in working if p.get("countryCode") == country_code.upper()]

    def get_proxies_by_type(self, proxy_type: str) -> List[Dict[str, Any]]:
        """
        Get proxies filtered by type.
        
        Args:
            proxy_type: Proxy type (HTTP, SOCKS4, SOCKS5)
            
        Returns:
            List of proxies of specified type
        """
        working = self.get_working_proxies()
        return [p for p in working if p.get("Type", "").upper() == proxy_type.upper()]


def main():
    """Example usage of the ProxyManager class."""
    
    # Initialize proxy manager
    pm = ProxyManager()
    
    # Scrape and save proxies
    print("🔍 Scraping proxies...")
    if pm.scrape_and_save_proxies():
        print("✅ Proxy scraping completed")
    else:
        print("❌ Proxy scraping failed")
        return
    
    # Test all proxies
    print("\n🧪 Testing proxies...")
    working_proxies = pm.test_all_proxies(max_proxies=50)  # Test first 50 proxies
    
    # Display results
    print(f"\n📊 Results:")
    print(f"Total working proxies: {len(working_proxies)}")
    
    if working_proxies:
        # Show fastest proxies
        fastest = pm.get_fastest_proxies(5)
        print(f"\n🚀 Top 5 fastest proxies:")
        for i, proxy in enumerate(fastest, 1):
            print(f"{i}. {proxy['IP Address']}:{proxy['Port']} - {proxy['response_time']}s - {proxy.get('country', 'Unknown')}")
        
        # Show proxies by type
        for ptype in ['HTTP', 'SOCKS4', 'SOCKS5']:
            typed_proxies = pm.get_proxies_by_type(ptype)
            if typed_proxies:
                print(f"\n🔧 {ptype} proxies: {len(typed_proxies)}")


if __name__ == "__main__":
    main()