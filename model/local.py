import requests

class ProxyTester:
    """
    A class to test HTTP and HTTPS requests through a proxy server.

    Attributes:
    ----------
    proxy_address : str
        The address of the proxy server to be used for requests.

    Methods:
    -------
    send_http(url: str):
        Sends an HTTP request to the specified URL through the proxy server and returns the HTML content.

    send_https(url: str):
        Sends an HTTPS request to the specified URL through the proxy server and returns the HTML content.
    """
    
    def __init__(self, proxy_address):
        """
        Initializes the ProxyTester with the provided proxy address.

        Parameters:
        ----------
        proxy_address : str
            The address of the proxy server to be used for requests.
        """
        self.proxies = {
            "http": proxy_address,
            "https": proxy_address,
        }

    def send_http(self, url):
        """
        Sends an HTTP request to the specified URL through the proxy server and returns the HTML content.

        Parameters:
        ----------
        url : str
            The URL to which the HTTP request is to be sent.

        Returns:
        -------
        str
            The HTML content of the response.
        """
        try:
            response = requests.get(url, proxies=self.proxies)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response
        except Exception as e:
            return f"HTTP Request Error: {e}"

    def send_https(self, url):
        """
        Sends an HTTPS request to the specified URL through the proxy server and returns the HTML content.

        Parameters:
        ----------
        url : str
            The URL to which the HTTPS request is to be sent.

        Returns:
        -------
        str
            The HTML content of the response.
        """
        try:
            response = requests.get(url, proxies=self.proxies)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response
        except Exception as e:
            return f"HTTPS Request Error: {e}"

# Example usage:
if __name__ == "__main__":
    proxy_address = "http://127.0.0.1:8888"
    tester = ProxyTester(proxy_address)
    
    # Test HTTP request
    print("Testing HTTP request:")
    http_content = tester.send_http("http://example.com")
    print(http_content[:500])  # Print the first 500 characters of the HTTP response

    # Test HTTPS request
    print("Testing HTTPS request:")
    https_content = tester.send_https("https://example.com")
    print(https_content[:500])  # Print the first 500 characters of the HTTPS response
