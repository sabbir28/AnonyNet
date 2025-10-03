from model.ProxyNet import ProxyManager
from model.AnonyNetProxyServer import AnonyNetProxyServer

if __name__ == "__main__":
    # Quick start
    pm = ProxyManager()
    working = pm.test_all_proxies(max_workers=64)
    fastest = pm.get_fastest_proxies(1)
    
    # Start proxy server
    proxy = AnonyNetProxyServer()
    proxy.start()

