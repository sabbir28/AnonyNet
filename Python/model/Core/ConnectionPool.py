
# =============================================================================
# Supporting Components
# =============================================================================

class ConnectionPool:
    """Simple connection pool."""
    
    def __init__(self):
        self.pool = {}
        self.lock = threading.Lock()
        
    def get_connection(self, host: str, port: int) -> socket.socket:
        """Get connection from pool or create new."""
        key = (host, port)
        
        with self.lock:
            if key in self.pool and self.pool[key]:
                sock = self.pool[key].pop()
                try:
                    # Test if socket is still alive
                    sock.getpeername()
                    return sock
                except:
                    pass
                    
        # Create new connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((host, port))
        return sock
        
    def return_connection(self, host: str, port: int, sock: socket.socket):
        """Return connection to pool."""
        key = (host, port)
        
        with self.lock:
            if key not in self.pool:
                self.pool[key] = []
                
            if len(self.pool[key]) < 10:  # Max 10 connections per upstream
                self.pool[key].append(sock)
            else:
                try:
                    sock.close()
                except:
                    pass