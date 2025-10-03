from flask import Flask, request

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def catch_all(path):
    # Print request method
    print(f"\n--- Received {request.method} request ---")
    
    # Print URL path
    print(f"Path: /{path}")
    
    # Print query parameters
    if request.args:
        print("Query Parameters:")
        for key, value in request.args.items():
            print(f"  {key}: {value}")
    
    # Print headers
    print("\nHeaders:")
    for key, value in request.headers.items():
        print(f"  {key}: {value}")
    
    # Print request body (if any)
    if request.data:
        print("\nBody:")
        print(request.data.decode('utf-8'))
    
    return "Request received!\n"

if __name__ == "__main__":
    # Run server on all interfaces, port 8080
    app.run(host="0.0.0.0", port=8080, debug=True)
