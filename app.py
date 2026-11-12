from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    from dotenv import load_dotenv, set_key

    load_dotenv()
except ImportError:
    set_key = None

from flask import Flask, jsonify, render_template, request, send_from_directory

import tools
from agent import Agent

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

agent = Agent()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.json.ensure_ascii = False

_DEFAULT_THREADS = str(max(1, min(8, (os.cpu_count() or 4) // 2)))

CONFIG_GROUPS = [
    {
        "name": "Web search",
        "fields": [
            {
                "key": "BRAVE_API_KEY",
                "label": "Brave Search API key",
                "type": "secret",
                "default": "",
                "hint": "Optional. DuckDuckGo works without a key. Free keys: brave.com/search/api",
            },
            {
                "key": "MAX_SOURCES",
                "label": "Max sources",
                "type": "int",
                "default": "3",
                "min": 1,
                "max": 10,
                "hint": "Sources cited in the answer; the same number of top pages is read in full.",
            },
            {
                "key": "HTTP_TIMEOUT",
                "label": "HTTP timeout (seconds)",
                "type": "int",
                "default": "10",
                "min": 1,
                "max": 120,
                "hint": "Timeout for search and page requests.",
            },
        ],
    },
    {
        "name": "Study cards",
        "fields": [
            {
                "key": "STUDY_CARDS_DIR",
                "label": "Study cards folder",
                "type": "text",
                "default": "study_cards",
                "hint": "Checked recursively before any web search. Relative paths resolve from the app folder.",
            },
        ],
    },
    {
        "name": "Model",
        "hint": "Model and server settings apply after a restart.",
        "restart": True,
        "fields": [
            {
                "key": "MAX_TOKENS",
                "label": "Max answer tokens",
                "type": "int",
                "default": "350",
                "min": 64,
                "max": 4096,
                "hint": "Longest answer the model may generate.",
                "restart": False,
            },
            {
                "key": "MODEL_REPO",
                "label": "Model repository",
                "type": "text",
                "default": "openbmb/MiniCPM5-2B-GGUF",
                "hint": "Hugging Face GGUF repository the weights come from.",
            },
            {
                "key": "MODEL_FILE",
                "label": "Model file",
                "type": "text",
                "default": "MiniCPM5-2B-Q4_K_M.gguf",
                "hint": "GGUF file downloaded from the repository.",
            },
            {
                "key": "MODEL_DIR",
                "label": "Model directory",
                "type": "text",
                "default": "models",
                "hint": "Where model weights are stored.",
            },
            {
                "key": "AUTO_DOWNLOAD",
                "label": "Auto download",
                "type": "bool",
                "default": "1",
                "hint": "Download missing weights automatically at startup.",
            },
            {
                "key": "N_CTX",
                "label": "Context window",
                "type": "int",
                "default": "6144",
                "min": 512,
                "max": 32768,
                "hint": "Total context tokens available to the model.",
            },
            {
                "key": "N_THREADS",
                "label": "CPU threads",
                "type": "int",
                "default": _DEFAULT_THREADS,
                "min": 1,
                "max": 64,
                "hint": "CPU threads used for inference.",
            },
            {
                "key": "N_GPU_LAYERS",
                "label": "GPU layers",
                "type": "int",
                "default": "0",
                "min": 0,
                "max": 128,
                "hint": "Layers offloaded to the GPU. 0 means CPU only.",
            },
            {
                "key": "N_BATCH",
                "label": "Batch size",
                "type": "int",
                "default": "512",
                "min": 32,
                "max": 4096,
                "hint": "Prompt batch size used by llama.cpp.",
            },
        ],
    },
    {
        "name": "Server",
        "hint": "Applied after a restart.",
        "restart": True,
        "fields": [
            {
                "key": "FLASK_RUN_HOST",
                "label": "Host",
                "type": "text",
                "default": "127.0.0.1",
                "hint": "Network interface the server listens on.",
            },
            {
                "key": "FLASK_RUN_PORT",
                "label": "Port",
                "type": "int",
                "default": "5000",
                "min": 1,
                "max": 65535,
                "hint": "Port the server listens on.",
            },
            {
                "key": "FLASK_DEBUG",
                "label": "Debug mode",
                "type": "bool",
                "default": "0",
                "hint": "Enables the Flask debug reloader.",
            },
        ],
    },
]


def _config_fields() -> dict:
    fields: dict[str, dict] = {}
    for group in CONFIG_GROUPS:
        for field in group["fields"]:
            fields[field["key"]] = {
                **field,
                "restart": field.get("restart", group.get("restart", False)),
            }
    return fields


def _normalize_setting(field: dict, raw) -> tuple[str | None, str]:
    value = str(raw).strip()
    kind = field["type"]
    if kind == "bool":
        lowered = value.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return None, "1"
        if lowered in {"0", "false", "no", "off", ""}:
            return None, "0"
        return "must be a boolean", value
    if kind == "int":
        try:
            number = int(value)
        except ValueError:
            return "must be a whole number", value
        if number < field["min"] or number > field["max"]:
            return f"must be between {field['min']} and {field['max']}", value
        return None, str(number)
    if not value and field["key"] != "BRAVE_API_KEY":
        return "cannot be empty", value
    if len(value) > 200:
        return "is too long (max 200 characters)", value
    return None, value


def _apply_live_config() -> None:
    cards_dir = Path(os.environ.get("STUDY_CARDS_DIR", "study_cards"))
    tools.STUDY_CARDS_DIR = cards_dir if cards_dir.is_absolute() else BASE_DIR / cards_dir
    tools.HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "10"))


@app.get("/")
def index():
    return render_template(
        "index.html",
        model=agent.model_name,
        card_folders=_card_folders(),
    )


@app.get("/study_cards/<path:filename>")
def study_card(filename: str):
    return send_from_directory(str(tools.STUDY_CARDS_DIR), filename)


def _card_slug(content: str) -> str:
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        if slug:
            return slug
        break
    return f"card-{datetime.now():%Y%m%d-%H%M%S}"


def _card_folders() -> list[str]:
    root = tools.STUDY_CARDS_DIR
    try:
        if not root.is_dir():
            return []
        return sorted(
            path.name
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )
    except OSError:
        return []


def _valid_card_name(name: str) -> bool:
    if not name or len(name) > 200 or name.startswith(".") or not name.lower().endswith(".md"):
        return False
    if "/" in name or "\\" in name or "\x00" in name:
        return False
    return not any(ord(char) < 32 for char in name)


@app.get("/api/study-cards")
def list_study_cards():
    root = tools.STUDY_CARDS_DIR
    cards = []
    try:
        if root.is_dir():
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() != ".md":
                    continue
                relative = path.relative_to(root)
                if any(part.startswith(".") for part in relative.parts):
                    continue
                rel = relative.as_posix()
                folder = relative.parent.as_posix()
                cards.append(
                    {
                        "name": path.name,
                        "folder": "" if folder == "." else folder,
                        "path": rel,
                        "url": f"/study_cards/{quote(rel)}",
                    }
                )
    except OSError:
        pass
    cards.sort(key=lambda card: card["path"].lower())
    return jsonify({"cards": cards, "folders": _card_folders()})


@app.post("/api/study-card")
def save_study_card():
    payload = request.get_json(silent=True) or {}
    content = payload.get("content")
    name = payload.get("name")
    folder = payload.get("folder")

    if not isinstance(content, str) or not content.strip():
        return jsonify({"error": "Card content is required."}), 400
    if len(content) > 200_000:
        return jsonify({"error": "Card is too large (max 200000 characters)."}), 400
    if name is not None and not isinstance(name, str):
        return jsonify({"error": "Card name must be a string."}), 400
    if folder is not None and not isinstance(folder, str):
        return jsonify({"error": "Folder must be a string."}), 400

    if name is not None and "md" not in name.split("."):
        name = name + ".md"

    root = tools.STUDY_CARDS_DIR
    folder = (folder or "").strip()
    if folder:
        if Path(folder).is_absolute():
            return jsonify({"error": "Invalid card folder."}), 400
        try:
            target_dir = (root / folder).resolve()
            target_dir.relative_to(root.resolve())
        except (OSError, ValueError):
            return jsonify({"error": "Invalid card folder."}), 400
        if not target_dir.is_dir():
            return jsonify({"error": f"Card folder '{folder}' does not exist."}), 404
    else:
        target_dir = root

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if name:
            if not _valid_card_name(name):
                return jsonify({"error": "Invalid card file name."}), 400
            path = target_dir / name
        else:
            stem = _card_slug(content)
            path = target_dir / f"{stem}.md"
            counter = 2
            while path.exists():
                path = target_dir / f"{stem}-{counter}.md"
                counter += 1
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        relative = path.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        return jsonify({"error": f"Could not save card: {exc}"}), 500

    return jsonify({"ok": True, "name": path.name, "path": f"/study_cards/{quote(relative)}"})


@app.get("/api/config")
def get_config():
    groups = []
    for group in CONFIG_GROUPS:
        fields = []
        for field in group["fields"]:
            fields.append(
                {
                    **field,
                    "value": os.environ.get(field["key"], field["default"]),
                    "restart": field.get("restart", group.get("restart", False)),
                }
            )
        groups.append({"name": group["name"], "hint": group.get("hint", ""), "fields": fields})
    return jsonify(
        {
            "env_path": str(ENV_PATH),
            "env_exists": ENV_PATH.exists(),
            "editable": set_key is not None,
            "groups": groups,
        }
    )

@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": agent.get_health(),
            "loading": agent.is_loading(),
            "model": agent.model_name,
            "backend": "llama.cpp · local",
        }
    )


@app.post("/api/stop")
def stop():
    agent.close()
    return jsonify({"ok": True, "status": agent.get_health()})


@app.post("/api/config")
def save_config():
    if set_key is None:
        return jsonify({"error": "python-dotenv is required to edit settings."}), 503

    payload = request.get_json(silent=True) or {}
    values = payload.get("values")
    if not isinstance(values, dict) or not values:
        return jsonify({"error": "values must be a non-empty object."}), 400

    fields = _config_fields()
    unknown = sorted(key for key in values if key not in fields)
    if unknown:
        return jsonify({"error": f"Unknown setting: {', '.join(unknown)}."}), 400

    clean: dict[str, str] = {}
    for key, raw in values.items():
        error, value = _normalize_setting(fields[key], raw)
        if error:
            return jsonify({"error": f"{fields[key]['label']}: {error}."}), 400
        clean[key] = value

    try:
        for key, value in clean.items():
            set_key(ENV_PATH, key, value)
            os.environ[key] = value
    except OSError as exc:
        return jsonify({"error": f"Could not write {ENV_PATH}: {exc}"}), 500

    _apply_live_config()
    restart_keys = sorted(key for key in clean if fields[key]["restart"])
    return jsonify(
        {
            "ok": True,
            "saved": sorted(clean),
            "restart_required": bool(restart_keys),
            "restart_keys": restart_keys,
        }
    )


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])
    search_cards_first = payload.get("search_study_cards_first", True)

    if not message:
        return jsonify({"error": "Message is required."}), 400
    if len(message) > 8000:
        return jsonify({"error": "Message is too long (max 8000 characters)."}), 400
    if history is not None and not isinstance(history, list):
        return jsonify({"error": "History must be a list."}), 400
    if not isinstance(search_cards_first, bool):
        return jsonify({"error": "search_study_cards_first must be a boolean."}), 400

    try:
        result = agent.run(
            message,
            history if isinstance(history, list) else [],
            search_study_cards_first=search_cards_first,
        )
    except Exception as exc:
        app.logger.exception("Chat request failed")
        return jsonify({"error": f"Agent error: {exc}"}), 500

    return jsonify(result)


if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug, threaded=True)



