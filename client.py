import requests
import webbrowser
import time

def check_server_available(url, timeout=5):
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False

def open_server_in_browser(server_url):
    while not check_server_available(server_url):
        print(f"Server at {server_url} is not available yet, retrying...")
        time.sleep(2)
    
    print(f"Server at {server_url} is now available.")
    webbrowser.open_new_tab(server_url)

if __name__ == "__main__":
    server_url = "http://192.168.10.5:8000"
    open_server_in_browser(server_url)