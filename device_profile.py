"""Device profile detection and hardware context for Iris."""

from dataclasses import dataclass, field
import os
import platform
import shutil
import sys
from typing import List, Dict, Any


@dataclass
class DeviceProfile:
    """Store hardware, OS, and software environment metadata."""

    os_name: str = "Windows"
    os_version: str = "11"
    os_full: str = "Microsoft Windows 11 Home Single Language"
    system_model: str = "HP Laptop 15s-fq5xxx"
    processor: str = "12th Gen Intel(R) Core(TM) i5-1235U"
    gpu: str = "Intel(R) Iris(R) Xe Graphics (Integrated, No CUDA)"
    has_cuda: bool = False
    ram_gb: float = 32.0
    architecture: str = "AMD64"
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    shells: List[str] = field(default_factory=lambda: ["powershell", "cmd"])
    available_tools: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a compact one-line hardware and OS summary."""
        cuda_status = "CUDA Supported" if self.has_cuda else "Integrated GPU (No CUDA)"
        return (
            f"OS: {self.os_full} ({self.architecture}) | CPU: {self.processor} | "
            f"RAM: {self.ram_gb:.0f}GB | GPU: {cuda_status} | Python: {self.python_version}"
        )


def detect_device_profile() -> DeviceProfile:
    """Detect current system environment with safe fallbacks."""
    os_name = platform.system()
    os_release = platform.release()
    arch = platform.machine()
    py_ver = sys.version.split()[0]

    # Detect installed tools and package managers
    tools = []
    candidates = ["git", "python", "pip", "winget", "choco", "curl", "powershell", "cmd"]
    for tool in candidates:
        if shutil.which(tool):
            tools.append(tool)

    # Detect RAM if psutil or ctypes is available, fallback to 32.0 GB
    ram_gb = 32.0
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        ram_gb = 32.0

    return DeviceProfile(
        os_name=os_name or "Windows",
        os_version=os_release or "11",
        os_full="Microsoft Windows 11 Home Single Language" if os_name == "Windows" else f"{os_name} {os_release}",
        system_model="HP Laptop 15s-fq5xxx",
        processor="12th Gen Intel(R) Core(TM) i5-1235U",
        gpu="Intel(R) Iris(R) Xe Graphics (Integrated, No CUDA)",
        has_cuda=False,
        ram_gb=ram_gb,
        architecture=arch or "AMD64",
        python_version=py_ver,
        shells=["powershell", "cmd"] if os_name == "Windows" else ["bash", "sh"],
        available_tools=tools,
    )


# Default cached profile for the active session
CURRENT_DEVICE = detect_device_profile()
