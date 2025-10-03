
class RateLimiter:
    """Simple rate limiter."""
    
    def __init__(self):
        self.requests = {}
        self.lock = threading.Lock()
        
    def check_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limit."""
        now = time.time()
        
        with self.lock:
            if client_ip not in self.requests:
                self.requests[client_ip] = []
                
            # Remove old requests (last 60 seconds)
            self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < 60]
            
            # Check limit (100 requests per minute)
            if len(self.requests[client_ip]) >= 100:
                return False
                
            self.requests[client_ip].append(now)
            return True