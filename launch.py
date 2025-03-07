import tkinter as tk
from tkinter import messagebox
import subprocess

def start_api_server():
    try:
        subprocess.Popen([r'venv\\python.exe', 'api_server.py'])
        messagebox.showinfo("启动服务端", "服务端已启动")
    except Exception as e:
        messagebox.showerror("错误", f"无法启动服务端: {e}")

def start_client():
    try:
        subprocess.Popen([r'venv\\python.exe', 'client.py'])
        messagebox.showinfo("启动客户端", "客户端已启动")
    except Exception as e:
        messagebox.showerror("错误", f"无法启动客户端: {e}")

root = tk.Tk()
root.title("选择启动模式")
root.geometry('300x200')
root.configure(bg='#f0f0f0')

frame = tk.Frame(root, bg='#f0f0f0')
frame.pack(expand=True)

button_server = tk.Button(frame, text="启动服务端", command=start_api_server, width=15)
button_server.pack(side=tk.TOP, pady=10)

button_client = tk.Button(frame, text="启动客户端", command=start_client, width=15)
button_client.pack(side=tk.TOP, pady=10)

root.mainloop()