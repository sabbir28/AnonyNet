import requests
from bs4 import BeautifulSoup
import json
import os

def fetch_proxy_list(url, headers):
    """
    Fetches the proxy list page content.
    
    Parameters:
        url (str): URL of the proxy list page.
        headers (dict): Headers to mimic a real browser request.
        
    Returns:
        str: HTML content of the proxy list page.
    """
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.content
    else:
        print("Failed to retrieve the webpage")
        return None

def parse_proxy_list(page_content):
    """
    Parses the proxy list from the HTML content.
    
    Parameters:
        page_content (str): HTML content of the proxy list page.
        
    Returns:
        list: A list of dictionaries containing proxy data.
    """
    soup = BeautifulSoup(page_content, 'html.parser')
    table_block = soup.find('div', class_='table_block')
    
    if not table_block:
        print("Failed to find the proxy table")
        return []
    
    rows = table_block.find('tbody').find_all('tr')
    proxies = []

    for row in rows:
        columns = row.find_all('td')
        ip_address = columns[0].text
        port = columns[1].text
        country = columns[2].find('span', class_='country').text
        city = columns[2].find('span', class_='city').text if columns[2].find('span', class_='city') else ''
        speed = columns[3].find('p').text.strip()
        proxy_type = columns[4].text
        anonymity = columns[5].text
        latest_update = columns[6].text

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
    
    return proxies

def save_proxies_to_json(proxies, file_path):
    """
    Saves the proxy data to a JSON file.
    
    Parameters:
        proxies (list): A list of dictionaries containing proxy data.
        file_path (str): Path to the JSON file.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as json_file:
        json.dump(proxies, json_file, indent=4)
    print(f"Proxy data has been written to {file_path}")

def main():
    # URL of the proxy list
    url = "https://hide.mn/en/proxy-list/"
    
    # Headers to mimic a real browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }
    
    # Fetching the proxy list page content
    page_content = fetch_proxy_list(url, headers)
    if page_content:
        # Parsing the proxy list
        proxies = parse_proxy_list(page_content)
        if proxies:
            # Saving the proxy data to a JSON file
            save_proxies_to_json(proxies, 'proxies/proxy_list.json')

if __name__ == "__main__":
    main()
