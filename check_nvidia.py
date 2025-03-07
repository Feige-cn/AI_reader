import subprocess
import os
import re
import sys
import platform
from typing import Tuple, Optional
from pathlib import Path
import ctypes

try:
    import torch  # 用于获取GPU计算能力
except ImportError:
    torch = None

base_dir = Path(__file__).parent.absolute()
cuda_dll_dir = os.path.join(base_dir, "cudnnbin")

def check_nvidia():
    print("="*40)
    print("NVIDIA 环境兼容性检查")
    print("="*40)
    
    try:
        setup_dll_path()
        load_critical_dlls()
        print("✅ DLL初始化成功")
    except Exception as e:
        print(f"❌ DLL初始化失败: {str(e)}")
        sys.exit(1)

    if check_compatibility():
        print("\n所有检查通过 ✅ 环境符合要求！")
    else:
        print("\n存在兼容性问题 ❌ 请根据提示修复！")
        # sys.exit(1)  # 返回非零退出码便于脚本判断

def setup_dll_path():
    # 修改 PATH 环境变量（确保优先级最高）
    if platform.system() == "Windows":
        os.environ["PATH"] = f"{cuda_dll_dir}{os.pathsep}{os.environ['PATH']}"

    # 使用 add_dll_directory
    if hasattr(os, "add_dll_directory") and os.path.exists(cuda_dll_dir):
        os.add_dll_directory(cuda_dll_dir)

def load_critical_dlls():
    if platform.system() != "Windows":
        return

    # 按依赖顺序加载
    critical_dlls = [
        "cudart64_12.dll",    # CUDA Runtime
        "cublas64_12.dll",    # 基础线性代数
        "cublasLt64_12.dll",  # cuBLAS轻量级版本
        "cusparse64_12.dll",  # 稀疏矩阵
        "curand64_10.dll",    # 随机数生成
        "cufft64_11.dll",     # 快速傅里叶变换
        "cusolver64_11.dll",  # 解算器
        "cudnn64_9.dll",      # cuDNN主库
        "cudnn_adv64_9.dll",  # 高级功能
        "cudnn_adv_infer64_8.dll",  # 高级推理
        "cudnn_cnn64_9.dll",       # 卷积神经网络
        "cudnn_cnn_infer64_8.dll", # CNN推理
        "cudnn_engines_precompiled64_9.dll",  # 预编译引擎
        "cudnn_engines_runtime_compiled64_9.dll",  # 运行时编译引擎
        "cudnn_graph64_9.dll",  # 图形优化
        "cudnn_heuristic64_9.dll",  # 启发式算法
        "cudnn_ops64_9.dll",  # 操作集
        "cudnn_ops_infer64_8.dll",  # 推理操作集
    ]
    
    missing_dlls = []
    for dll in critical_dlls:
        dll_path = os.path.join(cuda_dll_dir, dll)
        if not os.path.exists(dll_path):
            missing_dlls.append(dll)
            continue
            
        try:
            ctypes.windll.LoadLibrary(dll_path)
        except OSError as e:
            raise RuntimeError(f"加载 {dll} 失败: {str(e)}")
    
    if missing_dlls:
        raise RuntimeError(f"缺失关键DLL文件: {', '.join(missing_dlls)}")

# ================== 版本检测核心函数 ==================
def get_nvidia_driver_version() -> Tuple[int, ...]:
    """获取NVIDIA驱动版本（返回元组，例如 (525, 60, 13)）"""
    try:
        output = subprocess.check_output(
            ["nvidia-smi"],
            text=True,
            stderr=subprocess.STDOUT,
            shell=platform.system() == "Windows"
        )
    except FileNotFoundError:
        raise RuntimeError("未找到NVIDIA驱动，请确认已安装NVIDIA显卡驱动。")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"执行nvidia-smi失败: {e.output}")

    # 提取驱动版本（支持格式：525.60.13 或 516.94）
    driver_match = re.search(r'Driver Version:\s+(\d+\.\d+\.\d+|\d+\.\d+)', output)
    if not driver_match:
        raise RuntimeError("无法从nvidia-smi提取驱动版本。")
    
    version_str = driver_match.group(1)
    parts = list(map(int, version_str.split('.')))
    return tuple(parts + [0]*(3-len(parts)))  # 补齐三位

def get_cuda_version() -> Tuple[int, ...]:
    """从nvidia-smi获取系统支持的CUDA版本（返回元组，例如 (12, 1)）"""
    try:
        output = subprocess.check_output(
            ["nvidia-smi"],
            text=True,
            stderr=subprocess.STDOUT,
            shell=platform.system() == "Windows"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"无法获取CUDA版本: {e.output}")

    # 提取CUDA版本（例如：CUDA Version: 12.1）
    cuda_match = re.search(r'CUDA Version:\s+(\d+\.\d+)', output)
    if not cuda_match:
        raise RuntimeError("无法从nvidia-smi提取CUDA版本。")
    
    return tuple(map(int, cuda_match.group(1).split('.')))

def get_gpu_compute_capability() -> Optional[Tuple[int, int]]:
    """获取GPU计算能力（例如 (8, 6) 表示Ampere架构）"""
    if torch is not None and torch.cuda.is_available():
        device = torch.device("cuda:0")
        capability = torch.cuda.get_device_capability(device)
        return (capability[0], capability[1])
    else:
        # 备用方法：通过nvidia-smi获取GPU型号手动判断（示例）
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "-L"],
                text=True,
                stderr=subprocess.STDOUT,
                shell=platform.system() == "Windows"
            )
            if "A100" in output:
                return (8, 0)  # Ampere
            elif "V100" in output:
                return (7, 0)  # Volta
            elif "T4" in output:
                return (7, 5)  # Turing
        except:
            pass
    return None

# ================== 兼容性检查 ==================
def check_compatibility(
    min_driver: Tuple[int, int, int] = (528, 33, 13),
    min_cuda: Tuple[int, int] = (12, 1),
    min_compute_capability: Tuple[int, int] = (3, 5)
) -> bool:
    """综合检查驱动、CUDA版本和GPU计算能力"""
    all_ok = True

    try:
        # 检查驱动版本
        driver_version = get_nvidia_driver_version()
        required_driver_str = ".".join(map(str, min_driver))
        current_driver_str = ".".join(map(str, driver_version))
        
        if driver_version < min_driver:
            print(f"❌ 驱动版本过低: {current_driver_str} < {required_driver_str}")
            all_ok = False
        else:
            print(f"✅ 驱动版本符合要求: {current_driver_str} >= {required_driver_str}")
    except Exception as e:
        print(f"⚠️ 驱动检测失败: {str(e)}")
        all_ok = False

    try:
        # 检查CUDA版本
        cuda_version = get_cuda_version()
        required_cuda_str = ".".join(map(str, min_cuda))
        current_cuda_str = ".".join(map(str, cuda_version))
        
        if cuda_version < min_cuda:
            print(f"❌ CUDA版本过低: {current_cuda_str} < {required_cuda_str}")
            all_ok = False
        else:
            print(f"✅ CUDA版本符合要求: {current_cuda_str} >= {required_cuda_str}")
    except Exception as e:
        print(f"⚠️ CUDA检测失败: {str(e)}")
        all_ok = False

    # 检查GPU计算能力
    compute_capability = get_gpu_compute_capability()
    if compute_capability:
        cc_str = f"{compute_capability[0]}.{compute_capability[1]}"
        required_cc_str = f"{min_compute_capability[0]}.{min_compute_capability[1]}"
        
        if compute_capability < min_compute_capability:
            print(f"❌ GPU计算能力不足: {cc_str} < {required_cc_str}")
            all_ok = False
        else:
            print(f"✅ GPU计算能力符合: {cc_str} >= {required_cc_str}")
    else:
        print("⚠️ 无法自动检测GPU计算能力，请手动确认GPU型号（如RTX 30系列需Ampere架构以上）")
        all_ok = False

    if not all_ok:
        print("\n建议操作:")
        print("1. 升级驱动: https://www.nvidia.com/Download/index.aspx")
        print("2. 安装CUDA Toolkit: https://developer.nvidia.com/cuda-downloads")
        print("3. 确认GPU型号（需支持计算能力 >= {min_compute_capability[0]}.{min_compute_capability[1]})")
        if torch is None:
            print("提示: 安装PyTorch可提升检测精度 → pip install torch")

    return all_ok