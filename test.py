import requests

# Define the proxy
proxies = {
    "http": "http://127.0.0.1:8888",
    "https": "http://127.0.0.1:8888",
}

# Test HTTP request
try:
    response = requests.get("https://www.google.com/", proxies=proxies)
    print("HTTP Response Status Code:", response.status_code)
    print("HTTP Response Content:", response.text[:500])  # Print the first 500 characters
except Exception as e:
    print(f"HTTP Request Error: {e}")

# Test HTTPS request
try:
    response = requests.get("https://www.google.com/", proxies=proxies)
    print("HTTPS Response Status Code:", response.status_code)
    print("HTTPS Response Content:", response.text[:500])  # Print the first 500 characters
except Exception as e:
    print(f"HTTPS Request Error: {e}")
