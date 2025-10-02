from model.ProxyNet import ProxyManager

if __name__ == "__main__":
    # Quick start
    pm = ProxyManager()
    pm.scrape_and_save_proxies()
    working = pm.test_all_proxies(max_proxies=20)
    fastest = pm.get_fastest_proxies(5)