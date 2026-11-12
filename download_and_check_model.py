#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable

import requests

BASE_DIR = Path(__file__).resolve().parent

Progress = Callable[[int, int], None]

MIN_MODEL_BYTES = 100 * 1024 * 1024


def model_repo() -> str:
    return os.getenv("MODEL_REPO", "openbmb/MiniCPM5-2B-GGUF")


def model_file() -> str:
    return os.getenv("MODEL_FILE", "MiniCPM5-2B-Q4_K_M.gguf")


def model_path() -> Path:
    directory = Path(os.getenv("MODEL_DIR", "models"))
    if not directory.is_absolute():
        directory = BASE_DIR / directory
    return Path(os.getenv("MODEL_PATH", str(directory / model_file())))


def auto_download() -> bool:
    return os.getenv("AUTO_DOWNLOAD", "1").strip().lower() not in {"0", "false", "no"}


def model_url() -> str:
    return f"https://huggingface.co/{model_repo()}/resolve/main/{model_file()}"


def _has_gguf_magic(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


def model_ready() -> bool:
    path = model_path()

    try:
        if not path.is_file():
            return False
        if path.stat().st_size < MIN_MODEL_BYTES:
            return False
    except OSError:
        return False

    return _has_gguf_magic(path)


def ensure_model(progress: Progress | None = None) -> Path:
    path = model_path()

    if model_ready():
        return path

    if not auto_download():
        raise FileNotFoundError(
            f"Model not found at {path}. Run `python download_and_check_model.py` or set AUTO_DOWNLOAD=1."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")

    headers: dict[str, str] = {}
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with requests.get(model_url(), stream=True, headers=headers, timeout=(30, 120)) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)

        done = 0
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

    part.replace(path)
    return path


def _cli_progress(done: int, total: int) -> None:
    if total:
        percent = done * 100 / total
        sys.stdout.write(f"\r{percent:5.1f}%  {done / 1e9:.2f}/{total / 1e9:.2f} GB")
    else:
        sys.stdout.write(f"\r{done / 1e9:.2f} GB")
    sys.stdout.flush()


def main() -> int:
    path = model_path()

    if model_ready():
        print(f"Model ready: {path}")
        return 0

    print(f"Downloading {model_file()} to {path}")

    try:
        ensure_model(_cli_progress)
    except Exception as exc:
        print(f"\nDownload failed: {exc}")
        return 1

    print(f"\nModel ready: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
