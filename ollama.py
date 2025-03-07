import subprocess
import requests
import shutil
import os
import sys
import psutil
import re
from pathlib import Path

class Ollama:
    def __init__(self, callback=None):
        self.callback = callback
        self.base_dir = Path(__file__).parent.absolute()
        self.base_url = "http://127.0.0.1:11434"

    def is_ollama_installed(self):
        return shutil.which("ollama") is not None

    def start_ollama(self, ollama_path: Path):
        try:
            command = [str(ollama_path), 'serve']

            process = subprocess.Popen(
                command,
                env=os.environ.copy(),
                cwd=str(self.base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            print(f"[SERVICE] 启动命令: {' '.join(command)}")
        except Exception as e:
            print(f"启动Ollama失败: {e}")

    def stop_ollama(self, process_name="ollama"):
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                print(f"终止进程: {proc.info['name']} (PID: {proc.info['pid']})")
                try:
                    proc.terminate()
                except Exception as e:
                    print(f"无法终止进程 (PID: {proc.info['pid']}): {e}")

    def check_ollama_running(self):
        try:
            response = requests.get(self.base_url)
            return response.status_code == 200
        except Exception as e:
            return False

    def _validate_path(self, exe_path: Path, model_dir: Path):
        """ 路径验证 """
        if not exe_path.exists():
            raise FileNotFoundError(f"Ollama可执行文件缺失: {exe_path}")
        if not model_dir.exists():
            print(f"[WARN] 模型目录不存在，即将创建: {model_dir}")
            model_dir.mkdir(parents=True, exist_ok=True)

    def main(self):
        if self.is_ollama_installed():
            ollama_path = "ollama"  # 使用用户安装的Ollama
            print("使用系统Ollama启动")
        else:
            ollama_path = self.base_dir / "ollama" / (
                "ollama.exe" if sys.platform == "win32" else "ollama"
            )
            ollama_home = self.base_dir / "ollama" / "Models"
            self._validate_path(ollama_path, ollama_home)
            os.environ['OLLAMA_MODELS'] = str(ollama_home.resolve())
            print("使用内置Ollama启动")

        os.environ['OLLAMA_KEEP_ALIVE'] = str(0)

        if not self.check_ollama_running():
            self.start_ollama(ollama_path)

    def get_ollama_models(self) -> list:
        url = self.base_url + "/api/tags"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                models = response.json().get('models', [])
                if len(models) == 0:
                    _log =f"没有找到可用的Ollama本地模型。" 
                    print(_log)
                    self.callback(_log)
                return models
            else:
                _log =f"加载模型失败，HTTP Status Code: {response.status_code}" 
                print(_log)
                self.callback(_log)
        except Exception as e:
            print(f"An error occurred: {e}")

    def chat_with_ollama(self, data):
        # self.main()

        url = self.base_url + '/api/chat'
        try:
            response = requests.post(url, json=data)
            if response.status_code == 200:
                response_dict = response.json()
                if 'message' in response_dict and 'content' in response_dict['message']:
                    return self.remove_think_tags(response_dict['message']['content'])
            else:
                _log =f"Ollama请求失败，HTTP Status Code: {response.status_code}" 
                print(_log)
                self.callback(_log)
        except Exception as e:
            print(f"An error occurred: {e}")

    def remove_think_tags(self, content):
        if re.search(r'<think>.*?</think>', content, flags=re.DOTALL):
            return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        else:
            return content