import json
import socket
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse
from pathlib import Path
import os
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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
                    "ip_address": ip_address,
                    "port": port,
                    "country": country,
                    "city": city,
                    "speed": speed,
                    "type": proxy_type,
                    "anonymity": anonymity,
                    "latest_update": latest_update,
                    "scraped_at": datetime.now().isoformat()
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
            
        ip = proxy.get("ip_address", "")
        port_str = proxy.get("port", "0")
        
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": f"Invalid port: {port_str}",
                "response_time": 0.0,
                "ip_api": None,
            }
            
        ptype = (proxy.get("type") or "HTTP").upper()

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
            body = parsed_resp["body"]

            success = parsed_resp["headers"].splitlines()[0].upper().find("200 OK") != -1
            message = "Success" if success else f"Bad status: {parsed_resp['headers'].splitlines()[0] if parsed_resp['headers'] else 'no headers'}"

            ip_api = self._extract_ip_api(body) if body else None

            return {
                "success": success,
                "message": message,
                "response_time": round(elapsed, 3),
                "ip_api": ip_api,
            }

        except Exception as exc:
            elapsed = time.time() - start
            return {
                "success": False,
                "message": str(exc),
                "response_time": round(elapsed, 3),
                "ip_api": None,
            }

    def test_proxy_batch(self, proxies: List[Dict[str, Any]], target_url: Optional[str] = None, max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Test multiple proxies concurrently.
        
        Args:
            proxies: List of proxies to test
            target_url: URL to test against
            max_workers: Maximum number of concurrent threads
            
        Returns:
            List of working proxies
        """
        working_proxies = []
        
        def test_single_proxy(proxy):
            result = self.test_proxy(proxy, target_url)
            if result["success"]:
                record = proxy.copy()
                record.update({
                    "response_time": result["response_time"],
                    "tested_at": datetime.now().isoformat(),
                })
                
                if result.get("ip_api"):
                    record["ip_api"] = result["ip_api"]
                    # Update location info from ip_api
                    record.update({
                        "country": result["ip_api"].get("country"),
                        "country_code": result["ip_api"].get("countryCode"),
                        "region": result["ip_api"].get("region"),
                        "region_name": result["ip_api"].get("regionName"),
                        "city": result["ip_api"].get("city"),
                        "zip": result["ip_api"].get("zip"),
                        "lat": result["ip_api"].get("lat"),
                        "lon": result["ip_api"].get("lon"),
                        "timezone": result["ip_api"].get("timezone"),
                        "isp": result["ip_api"].get("isp"),
                        "org": result["ip_api"].get("org"),
                        "asn": result["ip_api"].get("as"),
                        "query_ip": result["ip_api"].get("query"),
                    })
                return record
            return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(test_single_proxy, proxy): proxy for proxy in proxies}
            
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    result = future.result()
                    if result:
                        working_proxies.append(result)
                        print(f"✅ Working: {result['ip_address']}:{result['port']} ({result.get('type', 'Unknown')}) - {result['response_time']}s")
                    else:
                        print(f"❌ Failed: {proxy['ip_address']}:{proxy['port']}")
                except Exception as exc:
                    print(f"❌ Error testing {proxy['ip_address']}:{proxy['port']}: {exc}")

        return working_proxies

    def test_all_proxies(self, target_url: Optional[str] = None, max_proxies: Optional[int] = None, max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Test all loaded proxies.
        
        Args:
            target_url: URL to test against
            max_proxies: Maximum number of proxies to test
            max_workers: Maximum number of concurrent threads
            
        Returns:
            List of working proxies
        """
        if not self.proxy_file.exists():
            print("❌ No proxy file found. Please scrape proxies first.")
            return []

        proxies = self.load_proxies_from_json()
        
        if max_proxies:
            proxies = proxies[:max_proxies]
            
        print(f"🧪 Testing {len(proxies)} proxies with {max_workers} concurrent workers...")
        
        working_proxies = self.test_proxy_batch(proxies, target_url, max_workers)
        
        self.save_proxies_to_json(working_proxies, self.working_file)
        print(f"✅ Saved {len(working_proxies)} working proxies to {self.working_file}")
        return working_proxies

    def test_untested_proxies(self, target_url: Optional[str] = None, max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Test proxies that are in proxy list but not in working list.
        
        Args:
            target_url: URL to test against
            max_workers: Maximum number of concurrent threads
            
        Returns:
            List of newly discovered working proxies
        """
        if not self.proxy_file.exists():
            print("❌ No proxy file found. Please scrape proxies first.")
            return []

        all_proxies = self.load_proxies_from_json(self.proxy_file)
        working_proxies = self.load_proxies_from_json(self.working_file)
        
        # Get IP:Port combinations of working proxies
        working_set = {f"{p['ip_address']}:{p['port']}" for p in working_proxies}
        
        # Find untested proxies
        untested_proxies = [
            p for p in all_proxies 
            if f"{p['ip_address']}:{p['port']}" not in working_set
        ]
        
        if not untested_proxies:
            print("✅ All proxies have been tested")
            return []
            
        print(f"🧪 Testing {len(untested_proxies)} untested proxies...")
        
        new_working_proxies = self.test_proxy_batch(untested_proxies, target_url, max_workers)
        
        if new_working_proxies:
            # Combine with existing working proxies
            all_working = working_proxies + new_working_proxies
            self.save_proxies_to_json(all_working, self.working_file)
            print(f"✅ Added {len(new_working_proxies)} new working proxies. Total: {len(all_working)}")
        
        return new_working_proxies

    def validate_working_proxies(self, target_url: Optional[str] = None, max_workers: int = 10) -> List[Dict[str, Any]]:
        """
        Re-test all working proxies and remove non-working ones.
        
        Args:
            target_url: URL to test against
            max_workers: Maximum number of concurrent threads
            
        Returns:
            List of still working proxies
        """
        if not self.working_file.exists():
            print("❌ No working proxies file found")
            return []

        working_proxies = self.load_proxies_from_json(self.working_file)
        
        if not working_proxies:
            print("❌ No working proxies to validate")
            return []
            
        print(f"🔍 Validating {len(working_proxies)} working proxies...")
        
        still_working = self.test_proxy_batch(working_proxies, target_url, max_workers)
        
        # Save updated list
        self.save_proxies_to_json(still_working, self.working_file)
        
        removed_count = len(working_proxies) - len(still_working)
        print(f"✅ Validation complete. Removed {removed_count} non-working proxies. {len(still_working)} proxies remain.")
        
        return still_working

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

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about proxies.
        
        Returns:
            Dictionary with proxy statistics
        """
        all_proxies = self.load_proxies_from_json(self.proxy_file) if self.proxy_file.exists() else []
        working_proxies = self.load_proxies_from_json(self.working_file) if self.working_file.exists() else []
        
        stats = {
            "total_proxies": len(all_proxies),
            "working_proxies": len(working_proxies),
            "success_rate": round(len(working_proxies) / len(all_proxies) * 100, 2) if all_proxies else 0,
        }
        
        # Count by type
        type_counts = {}
        for proxy in working_proxies:
            ptype = proxy.get("type", "Unknown")
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
        stats["by_type"] = type_counts
        
        # Count by country
        country_counts = {}
        for proxy in working_proxies:
            country = proxy.get("country", "Unknown")
            country_counts[country] = country_counts.get(country, 0) + 1
        stats["by_country"] = country_counts
        
        # Average response time
        if working_proxies:
            avg_time = sum(p.get("response_time", 0) for p in working_proxies) / len(working_proxies)
            stats["avg_response_time"] = round(avg_time, 3)
        
        return stats

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
        return [p for p in working if p.get("country_code") == country_code.upper()]

    def get_proxies_by_type(self, proxy_type: str) -> List[Dict[str, Any]]:
        """
        Get proxies filtered by type.
        
        Args:
            proxy_type: Proxy type (HTTP, SOCKS4, SOCKS5)
            
        Returns:
            List of proxies of specified type
        """
        working = self.get_working_proxies()
        return [p for p in working if p.get("type", "").upper() == proxy_type.upper()]

    def clear_working_proxies(self) -> bool:
        """
        Clear all working proxies.
        
        Returns:
            bool: True if successful
        """
        try:
            if self.working_file.exists():
                self.working_file.unlink()
            print("✅ Working proxies cleared")
            return True
        except Exception as e:
            print(f"❌ Failed to clear working proxies: {e}")
            return False


def main():
    """Example usage of the enhanced ProxyManager class."""
    
    # Initialize proxy manager
    pm = ProxyManager()
    
    # Display initial stats
    print("📊 Initial Proxy Statistics:")
    stats = pm.get_stats()
    print(f"   Total proxies in list: {stats['total_proxies']}")
    print(f"   Working proxies: {stats['working_proxies']}")
    print(f"   Success rate: {stats['success_rate']}%")
    
    # Scrape and save proxies
    print("\n🔍 Scraping new proxies...")
    if pm.scrape_and_save_proxies():
        print("✅ Proxy scraping completed")
    else:
        print("❌ Proxy scraping failed")
        return
    
    # Test all proxies with concurrent testing
    print("\n🧪 Testing all proxies concurrently...")
    working_proxies = pm.test_all_proxies(max_proxies=100, max_workers=20)
    
    # Test untested proxies
    print("\n🔍 Testing untested proxies...")
    new_proxies = pm.test_untested_proxies(max_workers=15)
    
    # Validate working proxies
    print("\n🔍 Validating working proxies...")
    valid_proxies = pm.validate_working_proxies(max_workers=15)
    
    # Display final results
    print(f"\n📊 Final Results:")
    stats = pm.get_stats()
    print(f"   Total proxies in list: {stats['total_proxies']}")
    print(f"   Working proxies: {stats['working_proxies']}")
    print(f"   Success rate: {stats['success_rate']}%")
    print(f"   Average response time: {stats.get('avg_response_time', 'N/A')}s")
    
    if stats['working_proxies'] > 0:
        # Show fastest proxies
        fastest = pm.get_fastest_proxies(5)
        print(f"\n🚀 Top 5 fastest proxies:")
        for i, proxy in enumerate(fastest, 1):
            print(f"   {i}. {proxy['ip_address']}:{proxy['port']} - {proxy['response_time']}s - {proxy.get('country', 'Unknown')}")
        
        # Show proxies by type
        print(f"\n🔧 Proxies by type:")
        for ptype, count in stats['by_type'].items():
            print(f"   {ptype}: {count}")
        
        # Show top countries
        print(f"\n🌍 Top countries:")
        sorted_countries = sorted(stats['by_country'].items(), key=lambda x: x[1], reverse=True)[:5]
        for country, count in sorted_countries:
            print(f"   {country}: {count}")


if __name__ == "__main__":
    main()