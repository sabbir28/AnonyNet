# AnonyNet Proxy Server
# Author: MD. SABBIR HOSHEN HOOWLADER
# Website: https://sabbir28.github.io/
# License: MIT License
# Description: AnonyNet is a proxy server designed to anonymize user requests by routing them through random public proxies. 
# It aims to enhance privacy and security while browsing by masking the user's IP address and encrypting data.
from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from flask import Flask, request, Response, render_template
import requests
import random
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import os
import urllib.parse
import mimetypes

app = Flask(__name__)

# List of public proxies (update with your own list)
proxies = [
    "http://127.0.0.1:8888"
]

# Setup logging
handler = RotatingFileHandler('logs/access.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

error_handler = RotatingFileHandler('logs/error.log', maxBytes=10000, backupCount=1)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
app.logger.addHandler(error_handler)


# Directory to save downloaded files
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER


def get_proxies():
    # Connect to the SQLite database
    conn = sqlite3.connect('proxies/db/working_proxies.db')
    cursor = conn.cursor()

    # Execute the query to get all proxies
    cursor.execute('SELECT * FROM proxies')
    proxies = cursor.fetchall()

    # Close the connection
    conn.close()

    return proxies

# Home screen route
@app.route('/')
def home():
    proxies = get_proxies()
    return render_template('index.html')


# Download screen route
@app.route('/download', methods=['GET', 'POST'])
def download_file():
    if request.method == 'POST':
        file_url = request.form.get('file_url')
        if file_url:
            try:
                # Disable file preview
                headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/octet-stream'}

                # Download the file
                response = requests.get(file_url, headers=headers, stream=True)

                # Parse the file name from the URL
                parsed_url = urllib.parse.urlparse(file_url)
                file_name = os.path.basename(parsed_url.path)
                file_path = os.path.join(app.config['DOWNLOAD_FOLDER'], file_name)

                # Save the file to the server
                with open(file_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                
                # Get file size in MB
                file_size = os.path.getsize(file_path) / (1024 * 1024)

                # Get the file MIME type
                mime_type, _ = mimetypes.guess_type(file_path)
                file_type = mime_type or 'Unknown'

                # Provide the link to download the file from the server
                download_link = url_for('download_saved_file', filename=file_name)
                return render_template('download.html', download_link=download_link, file_name=file_name, file_type=file_type, file_size=file_size, success=True)
            except Exception as e:
                return render_template('download.html', error=str(e))
    
    return render_template('download.html')

# Route to serve the downloaded file
@app.route('/downloads/<filename>')
def download_saved_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename, as_attachment=True)




@app.route('/tabil')
def index():
    proxies = get_proxies()
    return render_template('tabil.html', proxies=proxies)

@app.route('/proxy', methods=['GET', 'POST'])
def proxy():
    """
    Forwards requests through a randomly chosen proxy server.
    
    This endpoint handles both GET and POST requests. It selects a random proxy from the
    predefined list and forwards the request to the target server through that proxy.
    
    Returns:
        Response: The response from the target server, including content and headers.
    """
    try:
        # Get the target URL from the request
        target_url = request.args.get('url')
        if not target_url:
            return Response("Missing 'url' parameter.", status=400)

        # Choose a random proxy from the list
        selected_proxy = random.choice(proxies)
        if not selected_proxy:
            return Response("No proxies available.", status=500)

        proxies_dict = {
            "http": selected_proxy,
            "https": selected_proxy,
        }

        print(proxies_dict)

        # Log the request
        app.logger.info(f"Received {request.method} request for {target_url} using proxy {selected_proxy}")

        # Forward the request to the target server
        try:
            if request.method == 'POST':
                response = requests.post(target_url, data=request.form, proxies=proxies_dict, timeout=20)
            else:
                response = requests.get(target_url, params=request.args, timeout=20)

            # Log the response
            app.logger.info(f"Response status code: {response.status_code}")

            # Copy headers from the target response to the proxy response
            headers = {key: value for key, value in response.headers.items() if key.lower() != 'content-encoding'}

            # Return the response from the target server
            return Response(response.content, status=response.status_code, headers=headers)
        
        except requests.exceptions.Timeout:
            app.logger.error("Request timed out")
            return Response("The request timed out. Please try again later.", status=504)
        except requests.exceptions.ConnectionError:
            app.logger.error("Connection error occurred")
            return Response("A connection error occurred. Please try again later.", status=502)
        except requests.exceptions.RequestException as e:
            app.logger.error(f"An error occurred: {e}")
            return Response("An error occurred while processing your request.", status=500)

    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return Response("An error occurred while processing your request.", status=500)

if __name__ == '__main__':
    app.run(debug=True)
