from __future__ import annotations

import logging
import os
import re
import threading
import time

from model_store import MODEL_PATH, ensure_model, model_ready

logger = logging.getLogger(__name__)

THINK_RE = re.compile(r"<think>.*?</think>", re.S)
OPEN_THINK_RE = re.compile(r"<think>.*", re.S)
SPECIAL_RE = re.compile(r"<\|im_(?:start|end)\|>")


class LLMError(RuntimeError):
    pass


def clean_model_text(text: str) -> str:
    text = SPECIAL_RE.sub("", text or "")
    text = THINK_RE.sub("", text)
    text = OPEN_THINK_RE.sub("", text)
    text = text.replace("<|im_end|>", "").strip()
    return text


class LocalLlamaClient:
    def __init__(self) -> None:
        self.model = os.getenv("LLM_MODEL", "MiniCPM5-2B Q4_K_M")
        self.model_path = str(MODEL_PATH)
        self.n_ctx = int(os.getenv("N_CTX", "6144"))
        self.n_threads = int(os.getenv("N_THREADS", str(max(1, min(8, (os.cpu_count() or 4) // 2)))))
        self.n_gpu_layers = int(os.getenv("N_GPU_LAYERS", "0"))
        self.n_batch = int(os.getenv("N_BATCH", "512"))
        self.load_timeout = float(os.getenv("MODEL_LOAD_TIMEOUT", "300"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "350"))

        self._llm = None
        self._state = "idle"
        self._message = "Waiting to load MiniCPM5-2B."
        self._progress = 0
        self._load_seconds = None
        self._ready = threading.Event()
        self._state_lock = threading.Lock()
        self._generate_lock = threading.Lock()
        self._loader: threading.Thread | None = None

    def start(self) -> None:
        with self._state_lock:
            if self._loader and self._loader.is_alive():
                return
            if self._state == "ready":
                return
            self._ready.clear()
            self._state = "loading"
            self._message = "Starting MiniCPM5-2B…"
            self._progress = 0
            self._loader = threading.Thread(target=self._load, name="minicpm-loader", daemon=True)
            self._loader.start()

    def ensure_started(self) -> None:
        with self._state_lock:
            if self._state != "idle":
                return
        self.start()

    def _set_state(self, state: str, message: str, progress: int | None = None) -> None:
        with self._state_lock:
            self._state = state
            self._message = message
            if progress is not None:
                self._progress = max(0, min(100, int(progress)))

    def _download_progress(self, done: int, total: int) -> None:
        percent = int(done * 100 / total) if total else 0
        done_gb = done / 1_000_000_000
        total_gb = total / 1_000_000_000
        self._set_state(
            "downloading",
            f"Downloading MiniCPM5-2B · {done_gb:.1f}/{total_gb:.1f} GB",
            percent,
        )

    def _load(self) -> None:
        started = time.monotonic()
        try:
            if not model_ready():
                self._set_state("downloading", "Downloading MiniCPM5-2B weights…", 0)
            prepare_message = "Preparing MiniCPM5-2B weights…"
            self._set_state("downloading" if not model_ready() else "loading", prepare_message, 0)
            ensure_model(self._download_progress)
            self._set_state("loading", "Loading MiniCPM5-2B into memory…", 100)

            from llama_cpp import Llama

            llm = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=self.n_ctx,
                n_batch=self.n_batch,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                verbose=False,
            )
            self._llm = llm
            self._load_seconds = round(time.monotonic() - started, 2)
            self._set_state(
                "ready",
                f"MiniCPM5-2B ready · {self.n_threads} CPU threads · {self.n_ctx} ctx",
                100,
            )
        except Exception as exc:
            logger.exception("MiniCPM5-2B failed to load")
            message = f"Could not load MiniCPM5-2B: {exc}"
            if isinstance(exc, ModuleNotFoundError):
                message += " (start the app with ./run.sh so its virtualenv is used)"
            self._set_state("error", message, 0)
        finally:
            self._ready.set()

    def _wait_until_ready(self) -> None:
        self.start()
        if not self._ready.wait(self.load_timeout):
            raise LLMError(f"MiniCPM5-2B is still {self._state}: {self._message}")
        with self._state_lock:
            if self._state != "ready" or self._llm is None:
                raise LLMError(self._message)

    def _format_prompt(self, messages: list[dict[str, str]]) -> str:
        blocks: list[str] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = str(message.get("content", ""))
            if role == "assistant":
                blocks.append(
                    f"<|im_start|>assistant\n<think>\n\n</think>\n\n{content}<|im_end|>\n"
                )
            elif role == "system":
                blocks.append(f"<|im_start|>system\n{content}<|im_end|>\n")
            else:
                blocks.append(f"<|im_start|>user\n{content}<|im_end|>\n")
        blocks.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
        return "".join(blocks)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int | None = None,
        top_p: float = 0.9,
        timeout: float | None = None,
    ) -> str:
        self._wait_until_ready()
        prompt = self._format_prompt(messages)
        limit = max_tokens or self.max_tokens
        with self._generate_lock:
            try:
                output = self._llm.create_completion(
                    prompt=prompt,
                    max_tokens=limit,
                    temperature=temperature,
                    top_p=top_p,
                    repeat_penalty=1.05,
                    stop=["<|im_end|>", "<|im_start|>"],
                    echo=False,
                )
            except Exception as exc:
                raise LLMError(f"MiniCPM5-2B inference failed: {exc}") from exc

        try:
            text = output["choices"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("MiniCPM5-2B returned an unexpected response.") from exc

        text = clean_model_text(text)
        if not text:
            raise LLMError("MiniCPM5-2B returned an empty response.")
        return text

    def health(self) -> dict:
        with self._state_lock:
            state = self._state
            message = self._message
            progress = self._progress
            load_seconds = self._load_seconds
        return {
            "online": state == "ready",
            "status": state,
            "progress": progress,
            "message": message,
            "backend": "llama.cpp · local",
            "model": self.model,
            "model_file": str(MODEL_PATH),
            "context": self.n_ctx,
            "threads": self.n_threads,
            "gpu_layers": self.n_gpu_layers,
            "load_seconds": load_seconds,
        }
