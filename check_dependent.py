import torch
import onnxruntime as ort
import os
import subprocess
from pathlib import Path

base_dir = Path(__file__).parent.absolute()

def check_dependent():
    check_gpu_support()
    add_espeak_dependent()
    check_vc_redist()

def check_gpu_support():
    """
    检查 PyTorch 和 ONNX Runtime 的 GPU 支持状态，并打印详细信息。
    """
    print("=" * 40)
    print("Checking GPU support for PyTorch and ONNX Runtime")
    print("=" * 40)

    # 检查 PyTorch 的 GPU 支持
    print("[PyTorch]")
    if torch.cuda.is_available():
        print(f"✅ CUDA is available: {torch.cuda.is_available()}")
        print(f"CUDA version: {torch.version.cuda}")
        print(f"cuDNN version: {torch.backends.cudnn.version()}")
        print(f"Current GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("❌ CUDA is NOT available. Please check your PyTorch installation and GPU drivers.")

    # 检查 ONNX Runtime 的 GPU 支持
    print("\n[ONNX Runtime]")
    try:
        onnx_dll_path = base_dir / "venv" / "Lib" / "site-packages" / "onnxruntime" / "capi"
        os.add_dll_directory(str(onnx_dll_path))
        print(f"Device: {ort.get_device()}")
        providers = ort.get_available_providers()
        print(f"Available providers: {providers}")
        if 'CUDAExecutionProvider' in providers:
            print("✅ CUDAExecutionProvider is available.")
        else:
            print("❌ CUDAExecutionProvider is NOT available. Please check your ONNX Runtime installation.")
    except Exception as e:
        print(f"Error while checking ONNX Runtime GPU support: {e}")

    print("=" * 40)
    print("GPU support check completed.")
    print("=" * 40)

def add_espeak_dependent():
    print("=" * 40)
    print("check eSpeak installed.")
    try:
        phone_espeak_lib = str((base_dir / "eSpeak NG" / "libespeak-ng.dll").resolve())
        espeak_data_path = str((base_dir / "eSpeak NG" / "espeak-ng-data").resolve())
        espeak_path = str((base_dir / "eSpeak NG").resolve())
        os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = phone_espeak_lib
        os.environ['ESPEAK_DATA_PATH'] = espeak_data_path
        os.environ['PATH'] = os.environ['PATH'] + ";" + espeak_path
        print("✅ success")
        print("=" * 40)
    except Exception as e:
        print(f"❌ error\t{str(e)}")
        print("=" * 40)

def is_vc_redist_installed():
    # 检查是否安装了 Visual C++ Redistributable
    try:
        output = subprocess.check_output(["wmic", "product", "where", "name like '%Visual C++%'", "get", "name"])
        result = "Visual C++" in output.decode("utf-8")
        print(f"✅ {result}")
        return result
    except Exception as e:
        print(f"❌ False\t{str(e)}")
        return False


def check_vc_redist():
    print("=" * 40)
    print("check Visual C++ Redistributable.")
    if not is_vc_redist_installed():
        print("Visual C++ Redistributable is not installed. Installing...")
        vc_redist_path = os.path.join(base_dir, "resources", "VC_redist.x64.exe")
        print(vc_redist_path)
        if os.path.exists(vc_redist_path):
            try:
                subprocess.run([vc_redist_path, "/install", "/quiet", "/norestart"])

                if is_vc_redist_installed():
                    print("Visual C++ Redistributable has been successfully installed.")
                else:
                    print("Visual C++ Redistributable installation failed.")
            except Exception as e:
                print(str(e))
        else:
            print("Visual C++ Redistributable installer not found.")
    else:
        print("Visual C++ Redistributable is already installed.")
    print("=" * 40)