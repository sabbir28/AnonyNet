# AnonyNet Proxy Server

AnonyNet is a proxy server designed to enhance privacy and security by routing user requests through random public proxies. It masks the user's IP address and encrypts data to protect user anonymity while browsing.

## Features
- Anonymizes user requests by routing through random proxies.
- Supports both GET and POST requests.
- Easy to deploy and configure.

## Installation

To set up AnonyNet on your local machine, follow these steps:

1. **Clone the Repository**
    ```bash
    git clone https://github.com/sabbir28/AnonyNet.git
    cd AnonyNet
    ```

2. **Install Dependencies**
    Ensure you have Python 3 installed, then install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

3. **Run the Server**
    Start the server using:
    ```bash
    python app.py
    ```

    By default, the server will run on `http://127.0.0.1:5000`.

## Usage

To use the proxy server, send requests to the `/proxy` endpoint:

- **GET Request Example**
    ```bash
    curl "http://127.0.0.1:5000/proxy?url=http://example.com"
    ```

- **POST Request Example**
    ```bash
    curl -X POST "http://127.0.0.1:5000/proxy" -d "url=http://example.com"
    ```

The server will forward your request through a random proxy and return the response from the target server.

## Configuration

Edit the `app.py` file to update the list of proxies:
```python
proxies = [
    "http://proxy1.com:8080",
    "http://proxy2.com:8080",
    "http://proxy3.com:8080"
]
```

Replace the placeholder proxies with your own list of working proxies.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the [MIT License](LICENSE). See the LICENSE file for details.

## Author

MD. SABBIR HOSHEN HOOWLADER  
Website: [https://sabbir28.github.io/](https://sabbir28.github.io/)
