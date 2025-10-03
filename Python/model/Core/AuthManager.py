
class AuthManager:
    """Simple authentication manager."""
    
    def __init__(self):
        self.allowed_ips = set()
        
    def check_access(self, context: ConnectionContext) -> bool:
        """Check if client is allowed."""
        client_ip = context.client_addr[0]
        
        # Allow all by default - add your ACL logic here
        return True
        
        # Example: Block specific IPs
        # blocked_ips = {'192.168.1.100', '10.0.0.5'}
        # return client_ip not in blocked_ips