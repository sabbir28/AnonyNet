import requests
from bs4 import BeautifulSoup
import json

# URL of the proxy list
url = "https://hide.mn/en/proxy-list/"

# Headers to mimic a real browser request
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive'
}

# Sending a request to the webpage with headers
response = requests.get(url, headers=headers)
if response.status_code == 200:
    page_content = response.content
else:
    print("Failed to retrieve the webpage")
    exit()

# Parsing the HTML content
soup = BeautifulSoup(page_content, 'html.parser')

# Finding the table block
table_block = soup.find('div', class_='table_block')
if not table_block:
    print("Failed to find the proxy table")
    exit()

# Extracting the table rows
rows = table_block.find('tbody').find_all('tr')

# List to hold proxy data
proxies = []

# Iterating over rows to extract proxy data
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

    # Creating a dictionary for each proxy
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

    # Adding the proxy data to the list
    proxies.append(proxy_data)

# Writing the proxy data to a JSON file
with open('proxies/proxy_list.json', 'w') as json_file:
    json.dump(proxies, json_file, indent=4)

print("Proxy data has been written to proxy_list.json")
