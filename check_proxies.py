import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# List of public proxies (update with your own list)
proxies = [
    "http://proxy1.com:8080",
    "http://proxy2.com:8080",
    "http://proxy3.com:8080"
]

# List to store working proxies
working_proxies = []

# Test URL
test_url = "http://www.example.com"

def check_proxy(proxy):
    proxies_dict = {
        "http": proxy,
        "https": proxy,
    }
    try:
        response = requests.get(test_url, proxies=proxies_dict, timeout=5)
        if response.status_code == 200:
            print(f"Proxy {proxy} is alive")
            return proxy
    except requests.RequestException as e:
        print(f"Proxy {proxy} failed: {e}")
    return None

def find_working_proxies(proxies):
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_proxy = {executor.submit(check_proxy, proxy): proxy for proxy in proxies}
        for future in as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            try:
                result = future.result()
                if result:
                    working_proxies.append(result)
            except Exception as e:
                print(f"Error checking proxy {proxy}: {e}")

    print("Working proxies:", working_proxies)
    return working_proxies

if __name__ == "__main__":
    find_working_proxies(proxies)
