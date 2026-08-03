"""Lazy local model adapters for server-side BGE-M3 and Qwen2.5-7B execution."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterable


def model_file_manifest(model_dir: str | Path) -> dict:
    root = Path(model_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Local model directory not found: {root}")
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        stat = path.stat()
        files.append({"path": path.relative_to(root).as_posix(), "bytes": stat.st_size})
    identity = json.dumps(files, ensure_ascii=False, separators=(",", ":"))
    return {
        "path": root.as_posix(),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "structure_sha256": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "files": files,
    }


def cuda_runtime_manifest(*, require_cuda: bool = False) -> dict:
    """Return an auditable CUDA runtime snapshot and optionally fail closed."""

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install requirements-server.txt before checking CUDA") from exc
    available = bool(torch.cuda.is_available())
    if require_cuda and not available:
        raise RuntimeError(
            "CUDA is required for this run but torch.cuda.is_available() is False. "
            "Do not fall back to CPU for the formal RP2 experiment."
        )
    devices = []
    if available:
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": torch.cuda.get_device_name(index),
                    "total_memory_bytes": int(properties.total_memory),
                    "compute_capability": f"{properties.major}.{properties.minor}",
                }
            )
    return {
        "torch_version": str(torch.__version__),
        "torch_compiled_cuda": str(torch.version.cuda or ""),
        "cuda_available": available,
        "cuda_device_count": int(torch.cuda.device_count()) if available else 0,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "devices": devices,
    }


class BgeM3Encoder:
    def __init__(
        self,
        model_path: str | Path,
        *,
        batch_size: int = 16,
        max_length: int = 8192,
        device: str | None = None,
        require_cuda: bool = False,
    ) -> None:
        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(f"BGE-M3 model not found: {path}")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install requirements-server.txt before loading BGE-M3") from exc
        self.runtime_manifest = cuda_runtime_manifest(require_cuda=require_cuda)
        if require_cuda and device and not str(device).startswith("cuda"):
            raise RuntimeError(f"BGE-M3 requires a CUDA device, got {device!r}")
        self.model = SentenceTransformer(
            str(path), trust_remote_code=True, device=device, local_files_only=True
        )
        self.model.max_seq_length = max_length
        self.batch_size = batch_size
        self.device = str(self.model.device)
        if require_cuda and not self.device.startswith("cuda"):
            raise RuntimeError(f"BGE-M3 loaded on {self.device}, not CUDA")

    def encode(self, texts: Iterable[str]):
        rows = list(texts)
        return self.model.encode(
            rows,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=len(rows) > self.batch_size,
        )


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model output contains no JSON object")
    payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Model JSON must be an object")
    return payload


class QwenLocalGenerator:
    def __init__(
        self,
        model_path: str | Path,
        *,
        device_map: str = "auto",
        dtype: str = "auto",
        require_cuda: bool = False,
    ) -> None:
        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(f"Qwen model not found: {path}")
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install requirements-server.txt before loading Qwen") from exc
        self.runtime_manifest = cuda_runtime_manifest(require_cuda=require_cuda)
        torch_dtype = "auto" if dtype == "auto" else getattr(torch, dtype)
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(path), trust_remote_code=True, local_files_only=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            str(path),
            trust_remote_code=True,
            local_files_only=True,
            device_map=device_map,
            torch_dtype=torch_dtype,
        ).eval()
        raw_device_map = getattr(self.model, "hf_device_map", {}) or {}
        self.device_map = {str(key): str(value) for key, value in raw_device_map.items()}
        offloaded = {
            key: value
            for key, value in self.device_map.items()
            if value in {"cpu", "disk"}
        }
        if require_cuda and offloaded:
            raise RuntimeError(f"Qwen contains CPU/disk-offloaded modules: {offloaded}")
        model_device = str(self.model.device)
        if require_cuda and not model_device.startswith("cuda") and not any(
            value.startswith("cuda") or value.isdigit() for value in self.device_map.values()
        ):
            raise RuntimeError(
                f"Qwen loaded on {model_device} with device_map={self.device_map}, not CUDA"
            )
        self.runtime_manifest.update(
            {
                "model_device": model_device,
                "model_device_map": self.device_map,
                "cpu_or_disk_offload": offloaded,
            }
        )
        self.last_metrics: dict = {}

    def count_chat_tokens(self, system_prompt: str, user_prompt: str) -> int:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return int(self.tokenizer([text], return_tensors="pt").input_ids.shape[1])

    def generate_json(self, system_prompt: str, user_prompt: str, *, max_new_tokens: int = 768) -> dict:
        import torch

        preparation_started = time.perf_counter()
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        preparation_elapsed = time.perf_counter() - preparation_started
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        generated = output[0][inputs.input_ids.shape[1] :]
        elapsed = time.perf_counter() - started
        self.last_metrics = {
            "prompt_tokens": int(inputs.input_ids.shape[1]),
            "generated_tokens": int(generated.shape[0]),
            "input_preparation_ms": preparation_elapsed * 1000,
            "elapsed_ms": elapsed * 1000,
            "tokens_per_second": float(generated.shape[0]) / elapsed if elapsed else 0.0,
            "cuda_peak_memory_bytes": int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0,
            "cuda_allocated_memory_bytes": int(torch.cuda.memory_allocated()) if torch.cuda.is_available() else 0,
            "model_device": str(self.model.device),
        }
        return _extract_json(self.tokenizer.decode(generated, skip_special_tokens=True))
