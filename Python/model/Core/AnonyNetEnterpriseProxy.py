
# =============================================================================
# Core Proxy Server
# =============================================================================

class AnonyNetEnterpriseProxy:
    """
    Working enterprise proxy server.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.running = False
        self.server_sockets = []
        
        # Core components
        self.connection_pool = ConnectionPool()
        self.routing_engine = RoutingEngine()
        self.rate_limiter = RateLimiter()
        self.auth_manager = AuthManager()
        
        # State
        self.active_connections = set()
        
        # Setup logging properly
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup proper logging without request_id errors."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('proxy.log')
            ]
        )
        self.logger = logging.getLogger('anonymet')
        
    def start(self):
        """Start the proxy server."""
        self.running = True
        self.logger.info("🚀 Starting AnonyNet Enterprise Proxy")
        
        # Create server sockets
        bind_configs = self.config.get('bind', [{'host': '0.0.0.0', 'port': 8888}])
        
        for bind_cfg in bind_configs:
            try:
                sock = self._create_server_socket(bind_cfg['host'], bind_cfg['port'])
                self.server_sockets.append(sock)
                self.logger.info(f"📍 Listening on {bind_cfg['host']}:{bind_cfg['port']}")
            except Exception as e:
                self.logger.error(f"Failed to bind {bind_cfg['host']}:{bind_cfg['port']}: {e}")
        
        # Start admin API in background
        admin_thread = threading.Thread(target=self._admin_server, daemon=True)
        admin_thread.start()
        
        # Main accept loop
        self._accept_loop()
        
    def _create_server_socket(self, host: str, port: int) -> socket.socket:
        """Create server socket."""
        # Try IPv6 first, fallback to IPv4
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        except:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            
        sock.listen(1024)
        sock.setblocking(False)
        return sock
        
    def _accept_loop(self):
        """Main accept loop."""
        self.logger.info("✅ Accept loop started")
        
        while self.running:
            try:
                read_sockets = [s for s in self.server_sockets if s.fileno() != -1]
                if not read_sockets:
                    time.sleep(0.1)
                    continue
                    
                readable, _, _ = select.select(read_sockets, [], [], 1.0)
                
                for sock in readable:
                    try:
                        client_socket, client_addr = sock.accept()
                        self._handle_new_connection(client_socket, client_addr)
                    except BlockingIOError:
                        continue
                    except Exception as e:
                        self.logger.error(f"Accept error: {e}")
                        
            except Exception as e:
                if self.running:  # Only log if we're still running
                    self.logger.error(f"Accept loop error: {e}")
                time.sleep(1)
                
    def _handle_new_connection(self, client_socket: socket.socket, client_addr: Tuple[str, int]):
        """Handle new client connection."""
        connection_id = str(uuid.uuid4())[:8]
        
        # Apply connection limits
        if len(self.active_connections) >= self.config.get('max_connections', 1000):
            self.logger.warning("Connection limit reached")
            client_socket.close()
            return
            
        # Create context and process
        context = ConnectionContext(
            connection_id=connection_id,
            client_socket=client_socket,
            client_addr=client_addr,
            start_time=datetime.now()
        )
        
        # Start in thread
        thread = threading.Thread(target=self._process_connection, args=(context,), daemon=True)
        thread.start()
        self.active_connections.add(connection_id)
        
    def _process_connection(self, context: ConnectionContext):
        """Process individual connection."""
        try:
            client_socket = context.client_socket
            client_socket.settimeout(10)
            
            # Receive initial data
            initial_data = client_socket.recv(4096)
            if not initial_data:
                return
                
            # Detect protocol
            if initial_data.startswith(b"CONNECT"):
                context.protocol = Protocol.HTTPS
                self._handle_https_connection(context, initial_data)
            else:
                context.protocol = Protocol.HTTP_1_1
                self._handle_http_connection(context, initial_data)
                
        except socket.timeout:
            self.logger.debug(f"Connection {context.connection_id} timeout")
        except Exception as e:
            self.logger.error(f"Connection {context.connection_id} error: {e}")
        finally:
            self.active_connections.discard(context.connection_id)
            try:
                context.client_socket.close()
            except:
                pass
                
    def _handle_https_connection(self, context: ConnectionContext, initial_data: bytes):
        """Handle HTTPS CONNECT tunnel."""
        # Extract target from CONNECT request
        target_host, target_port = self._parse_connect_request(initial_data)
        context.target_host = target_host
        context.target_port = target_port
        
        # Extract SNI
        context.sni = self._extract_sni(initial_data)
        
        self.logger.info(f"🔒 HTTPS: {context.client_addr[0]} -> {target_host}:{target_port} (SNI: {context.sni})")
        
        # Check access control
        if not self.auth_manager.check_access(context):
            self._send_http_response(context.client_socket, 403, "Forbidden")
            return
            
        # Check rate limiting
        if not self.rate_limiter.check_limit(context.client_addr[0]):
            self._send_http_response(context.client_socket, 429, "Too Many Requests")
            return
            
        # Route to appropriate upstream
        upstream = self.routing_engine.route(context)
        if not upstream:
            upstream = UpstreamConfig(host=target_host, port=target_port)
            
        # Establish tunnel
        self._establish_tunnel(context, upstream)
        
    def _handle_http_connection(self, context: ConnectionContext, initial_data: bytes):
        """Handle HTTP request."""
        request = self._parse_http_request(initial_data)
        context.request = request
        
        target_host = request.headers.get('Host', '').split(':')[0]
        context.target_host = target_host
        
        self.logger.info(f"🌐 HTTP: {context.client_addr[0]} -> {target_host} {request.method} {request.path}")
        
        # Check access control
        if not self.auth_manager.check_access(context):
            self._send_http_response(context.client_socket, 403, "Forbidden")
            return
            
        # Check rate limiting
        if not self.rate_limiter.check_limit(context.client_addr[0]):
            self._send_http_response(context.client_socket, 429, "Too Many Requests")
            return
            
        # Route request
        upstream = self.routing_engine.route(context)
        if not upstream:
            upstream = UpstreamConfig(host=target_host, port=80)
            
        # Forward request
        self._forward_http_request(context, upstream, request)
        
    def _establish_tunnel(self, context: ConnectionContext, upstream: UpstreamConfig):
        """Establish TLS tunnel."""
        upstream_sock = None
        try:
            # Connect to upstream
            upstream_sock = self.connection_pool.get_connection(upstream.host, upstream.port)
            
            # Send connection established
            context.client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            
            # Tunnel data
            self._tunnel_data(context.client_socket, upstream_sock, context.connection_id)
            
        except Exception as e:
            self.logger.error(f"Tunnel failed: {e}")
        finally:
            if upstream_sock:
                self.connection_pool.return_connection(upstream.host, upstream.port, upstream_sock)
                
    def _forward_http_request(self, context: ConnectionContext, upstream: UpstreamConfig, request: HTTPRequest):
        """Forward HTTP request."""
        upstream_sock = None
        try:
            upstream_sock = self.connection_pool.get_connection(upstream.host, upstream.port)
            
            # Send request
            upstream_sock.send(request.raw_data)
            
            # Receive and forward response
            while True:
                data = upstream_sock.recv(65536)
                if not data:
                    break
                context.client_socket.send(data)
                
        except Exception as e:
            self.logger.error(f"HTTP forward failed: {e}")
        finally:
            if upstream_sock:
                self.connection_pool.return_connection(upstream.host, upstream.port, upstream_sock)
                
    def _tunnel_data(self, client_sock: socket.socket, upstream_sock: socket.socket, conn_id: str):
        """Tunnel data between client and upstream."""
        sockets = [client_sock, upstream_sock]
        bytes_up = 0
        bytes_down = 0
        
        while True:
            try:
                read_ready, _, _ = select.select(sockets, [], [], 30)
                
                if not read_ready:
                    break
                    
                for sock in read_ready:
                    data = sock.recv(65536)
                    if not data:
                        return
                        
                    if sock is client_sock:
                        upstream_sock.send(data)
                        bytes_up += len(data)
                    else:
                        client_sock.send(data)
                        bytes_down += len(data)
                        
                # Log every 1MB transferred
                if bytes_up + bytes_down > 1024 * 1024:
                    self.logger.debug(f"📊 Tunnel {conn_id}: ↑{bytes_up} ↓{bytes_down}")
                    bytes_up = bytes_down = 0
                    
            except Exception as e:
                self.logger.debug(f"Tunnel {conn_id} closed: {e}")
                break
                
    def _parse_connect_request(self, data: bytes) -> Tuple[str, int]:
        """Parse CONNECT request."""
        try:
            lines = data.decode('utf-8', errors='ignore').split('\r\n')
            first_line = lines[0]
            parts = first_line.split()
            if len(parts) >= 2:
                target = parts[1]
                if ':' in target:
                    host, port_str = target.split(':', 1)
                    return host, int(port_str)
                else:
                    return target, 443
        except:
            pass
        return '', 443
        
    def _parse_http_request(self, data: bytes) -> HTTPRequest:
        """Parse HTTP request."""
        try:
            lines = data.decode('utf-8', errors='ignore').split('\r\n')
            first_line_parts = lines[0].split()
            
            method = first_line_parts[0] if first_line_parts else 'GET'
            path = first_line_parts[1] if len(first_line_parts) > 1 else '/'
            
            headers = {}
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
                    
            return HTTPRequest(method=method, path=path, headers=headers, raw_data=data)
        except:
            return HTTPRequest(method='GET', path='/', headers={}, raw_data=data)
            
    def _extract_sni(self, data: bytes) -> Optional[str]:
        """Extract SNI from ClientHello."""
        try:
            if len(data) < 5 or data[0] != 0x16:  # TLS handshake
                return None
                
            pos = 5  # Skip record header
            
            if len(data) < pos + 4 or data[pos] != 0x01:  # ClientHello
                return None
                
            pos += 4  # Skip handshake header
            pos += 34  # Skip version, random
            
            # Session ID
            if pos < len(data):
                session_id_len = data[pos]
                pos += 1 + session_id_len
                
            # Cipher suites
            if pos + 2 <= len(data):
                cipher_len = struct.unpack('>H', data[pos:pos+2])[0]
                pos += 2 + cipher_len
                
            # Compression methods
            if pos < len(data):
                compression_len = data[pos]
                pos += 1 + compression_len
                
            # Extensions
            if pos + 2 <= len(data):
                extensions_len = struct.unpack('>H', data[pos:pos+2])[0]
                pos += 2
                end_pos = pos + extensions_len
                
                while pos + 4 <= end_pos and pos < len(data):
                    ext_type = struct.unpack('>H', data[pos:pos+2])[0]
                    ext_len = struct.unpack('>H', data[pos+2:pos+4])[0]
                    
                    if ext_type == 0x0000:  # SNI extension
                        sni_data = data[pos+4:pos+4+ext_len]
                        return self._parse_sni_extension(sni_data)
                        
                    pos += 4 + ext_len
                    
        except Exception as e:
            self.logger.debug(f"SNI extraction failed: {e}")
            
        return None
        
    def _parse_sni_extension(self, data: bytes) -> Optional[str]:
        """Parse SNI extension."""
        try:
            if len(data) < 2:
                return None
                
            list_len = struct.unpack('>H', data[0:2])[0]
            pos = 2
            
            while pos + 3 <= len(data):
                name_type = data[pos]
                name_len = struct.unpack('>H', data[pos+1:pos+3])[0]
                
                if name_type == 0 and pos + 3 + name_len <= len(data):
                    return data[pos+3:pos+3+name_len].decode('ascii')
                    
                pos += 3 + name_len
                
        except:
            pass
            
        return None
        
    def _send_http_response(self, sock: socket.socket, status: int, message: str):
        """Send HTTP response."""
        response = f"HTTP/1.1 {status} {message}\r\n\r\n"
        sock.send(response.encode())
        
    def _admin_server(self):
        """Simple admin API server."""
        try:
            admin_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            admin_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            admin_port = self.config.get('admin_port', 8889)
            admin_sock.bind(('127.0.0.1', admin_port))
            admin_sock.listen(5)
            admin_sock.settimeout(1)
            
            self.logger.info(f"🛠️  Admin API on 127.0.0.1:{admin_port}")
            
            while self.running:
                try:
                    client, addr = admin_sock.accept()
                    self._handle_admin_request(client)
                except socket.timeout:
                    continue
                except:
                    break
                    
        except Exception as e:
            self.logger.error(f"Admin API error: {e}")
            
    def _handle_admin_request(self, client: socket.socket):
        """Handle admin request."""
        try:
            request = client.recv(4096).decode()
            
            if '/health' in request:
                health = {
                    'status': 'healthy',
                    'active_connections': len(self.active_connections),
                    'timestamp': datetime.now().isoformat()
                }
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{json.dumps(health)}"
            elif '/stats' in request:
                stats = {
                    'connections_handled': 'N/A',
                    'uptime': 'N/A'
                }
                response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{json.dumps(stats)}"
            else:
                response = "HTTP/1.1 404 Not Found\r\n\r\n"
                
            client.send(response.encode())
        except:
            pass
        finally:
            client.close()
            
    def stop(self):
        """Stop the proxy."""
        self.logger.info("🛑 Stopping proxy...")
        self.running = False
        
        for sock in self.server_sockets:
            try:
                sock.close()
            except:
                pass
                
        self.logger.info("✅ Proxy stopped")