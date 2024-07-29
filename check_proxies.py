import requests
import json
import sqlite3
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Path to the JSON file
json_file_path = 'proxies/proxy_list.json'

# Path to the SQL and CSV files
sql_file_path = 'working_proxies.db'
csv_file_path = 'working_proxies.csv'

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
    
    # Extract proxy addresses from the JSON data
    proxies = [f"http://{proxy['IP Address']}:{proxy['Port']}" for proxy in proxy_list]

    # Find working proxies
    find_working_proxies(proxies)
    
    # Save working proxies to SQL and CSV files
    save_to_sql(working_proxies)
    save_to_csv(working_proxies)
