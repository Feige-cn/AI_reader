import psutil

def get_all_ips():
    ips = {}
    interfaces = psutil.net_if_addrs()
    for interface_name, interface_addresses in interfaces.items():
        for address in interface_addresses:
            if str(address.family) == 'AddressFamily.AF_INET':
                ips[interface_name] = address.address
    return ips

def get_lan_ip() -> list:
    all_ips = get_all_ips()
    lan_ips = []
    for interface, ip in all_ips.items():
        if ip.startswith('192.168'):
            lan_ips.append(ip)
    return lan_ips