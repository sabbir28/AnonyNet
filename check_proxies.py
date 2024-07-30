import requests
import json
import sqlite3
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import socks
import socket

# Paths to the JSON, SQL, and CSV files
json_file_path = 'proxies/proxy_list.json'
sql_file_path = 'proxies/db/working_proxies.db'
csv_file_path = 'proxies/db/working_proxies.csv'

# List to store working proxies
working_proxies = []

# Update test URLs for SOCKS proxies
test_urls = {
    "http": "http://www.example.com",
    "https": "https://www.example.com",
    "socks4": "http://www.example.com",
    "socks5": "http://www.example.com"
}

def check_proxy(proxy):
    proxy_type = proxy['Type'].lower()
    proxy_address = f"{proxy_type}://{proxy['IP Address']}:{proxy['Port']}"
    
    # For SOCKS proxies, use the SOCKS library
    if proxy_type in ["socks4", "socks5"]:
        socks.set_default_proxy(socks.SOCKS4 if proxy_type == "socks4" else socks.SOCKS5, proxy['IP Address'], int(proxy['Port']))
        socket.socket = socks.socksocket
    
    proxies_dict = {proxy_type: proxy_address}
    
    try:
        response = requests.get(test_urls.get(proxy_type, "http://www.example.com"), proxies=proxies_dict, timeout=5)
        if response.status_code == 200:
            print(f"Proxy {proxy_address} is alive")
            return proxy_address
    except requests.RequestException as e:
        print(f"Proxy {proxy_address} failed: {e}")
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

def save_to_sql(proxies):
    conn = sqlite3.connect(sql_file_path)
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy TEXT NOT NULL
        )
    ''')

    # Insert working proxies into the table
    cursor.executemany('INSERT INTO proxies (proxy) VALUES (?)', [(proxy,) for proxy in proxies])

    conn.commit()
    conn.close()
    print(f"Working proxies have been written to {sql_file_path}")

def save_to_csv(proxies):
    if os.path.dirname(csv_file_path):
        os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    with open(csv_file_path, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['Proxy'])
        for proxy in proxies:
            csvwriter.writerow([proxy])
    print(f"Working proxies have been written to {csv_file_path}")

if __name__ == "__main__":
    # Load proxies from the JSON file
    with open(json_file_path, 'r') as json_file:
        proxy_list = json.load(json_file)
    
    # Find working proxies
    find_working_proxies(proxy_list)
    
    # Save working proxies to SQL and CSV files
    save_to_sql(working_proxies)
    save_to_csv(working_proxies)
