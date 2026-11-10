#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_store import MODEL_PATH, ensure_model, model_ready


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
