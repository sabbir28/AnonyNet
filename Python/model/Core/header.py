
# =============================================================================
# Core Types & Configuration
# =============================================================================

class Protocol(Enum):
    HTTP_1_1 = "HTTP/1.1"
    HTTPS = "HTTPS"

@dataclass
class UpstreamConfig:
    host: str
    port: int
    weight: int = 1

@dataclass 
class HTTPRequest:
    method: str
    path: str
    headers: Dict[str, str]
    raw_data: bytes

@dataclass
class ConnectionContext:
    connection_id: str
    client_socket: socket.socket
    client_addr: Tuple[str, int]
    start_time: datetime
    protocol: Optional[Protocol] = None
    sni: Optional[str] = None
    target_host: Optional[str] = None
    target_port: Optional[int] = None
    request: Optional[HTTPRequest] = None