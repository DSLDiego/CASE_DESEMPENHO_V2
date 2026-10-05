"""Deteccao de hardware com fallback silencioso (nada quebra sem psutil/GPU)."""
from __future__ import annotations
import os
import shutil
import subprocess


def detect_hardware() -> dict:
    info: dict = {}
    # CPUs
    try:
        import psutil  # type: ignore
        info["cpu_logical"] = psutil.cpu_count(logical=True) or os.cpu_count() or 4
        info["cpu_physical"] = psutil.cpu_count(logical=False) or info["cpu_logical"]
        info["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
        info["cpu_source"] = "psutil"
    except Exception:
        info["cpu_logical"] = os.cpu_count() or 4
        info["cpu_physical"] = info["cpu_logical"]
        info["ram_gb"] = 0.0
        info["cpu_source"] = "os.cpu_count"
    # GPU NVIDIA
    gpu, vram, gpu_src = "", "", "nenhum"
    try:
        if shutil.which("nvidia-smi"):
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=8,
            )
            if out.returncode == 0 and out.stdout.strip():
                gpu = out.stdout.strip().splitlines()[0].strip()
                gpu_src = "nvidia-smi"
    except Exception:
        pass
    if not gpu:
        try:
            import torch  # type: ignore
            if torch.cuda.is_available():
                gpu = torch.cuda.get_device_name(0)
                gpu_src = "torch.cuda"
        except Exception:
            pass
    info["gpu"] = gpu
    info["gpu_src"] = gpu_src
    # Recomendacoes
    logical = int(info.get("cpu_logical") or 4)
    info["recommended_workers"] = max(2, min(logical, 15))
    info["max_workers"] = 128
    info["batch_options"] = [5, 10, 15, 20, 50, 100, "Auto"]
    info["gpu_helps"] = False
    info["gpu_note"] = (
        "Parsing PDF/Office/TXT e regex em Python sao CPU/I-O-bound; "
        "GPU so faria sentido com OCR/ML/tensores. Deteccao e informativa."
    )
    return info


def auto_batch(logical: int) -> int:
    return max(2, min(int(logical or 4), 15))
