#!/usr/bin/env python3
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Callable
import requests
import sys

BASE_DIR = Path(__file__).parents[1]
MODEL_REPO = os.getenv("MODEL_REPO", "openbmb/MiniCPM5-2B-GGUF")
MODEL_FILE = os.getenv("MODEL_FILE", "MiniCPM5-2B-Q4_K_M.gguf")
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(BASE_DIR / "models")))
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(MODEL_DIR / MODEL_FILE)))
AUTO_DOWNLOAD = os.getenv("AUTO_DOWNLOAD", "1").strip().lower() not in {"0", "false", "no"}

Progress = Callable[[int, int], None]


def model_url() -> str:
    return f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}"


def _has_gguf_magic(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


def model_ready() -> bool:
    if not MODEL_PATH.exists():
        return False
    if MODEL_PATH.stat().st_size < 100 * 1024 * 1024:
        return False
    return _has_gguf_magic(MODEL_PATH)


def ensure_model(progress: Progress | None = None) -> Path:
    if model_ready():
        return MODEL_PATH

    if not AUTO_DOWNLOAD:
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run scripts/download&check_model.py or set AUTO_DOWNLOAD=1."
        )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    part = MODEL_PATH.with_suffix(MODEL_PATH.suffix + ".part")
    headers: dict[str, str] = {}
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with requests.get(model_url(), stream=True, headers=headers, timeout=(30, 120)) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        done = 0
        started = time.monotonic()
        last_report = 0.0
        with part.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                done += len(chunk)
                if progress:
                    now = time.monotonic()
                    if now - last_report >= 0.4 or (total and done >= total):
                        progress(done, total)
                        last_report = now

    if not _has_gguf_magic(part):
        part.unlink(missing_ok=True)
        raise RuntimeError("Downloaded file is not a valid GGUF model.")

    part.replace(MODEL_PATH)
    return MODEL_PATH


def progress(done: int, total: int) -> None:
    if total:
        percent = done * 100 / total
        sys.stdout.write(f"\r{percent:5.1f}%  {done / 1e9:.2f}/{total / 1e9:.2f} GB")
    else:
        sys.stdout.write(f"\r{done / 1e9:.2f} GB")
    sys.stdout.flush()


def main() -> int:
    if model_ready():
        print(f"Model ready: {MODEL_PATH}")
        return 0

    print(f"Downloading MiniCPM5-2B to {MODEL_PATH}")
    try:
        ensure_model(progress)
    except Exception as exc:
        print(f"\nDownload failed: {exc}")
        return 1

    print(f"\nModel ready: {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

