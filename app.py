from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from flask import Flask, jsonify, render_template, request, send_from_directory

from agent import Agent
from llm import build_llm
from tools import STUDY_CARDS_DIR

llm = build_llm()
agent = Agent(llm)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.json.ensure_ascii = False


@app.get("/")
def index():
    llm.start()
    return render_template(
        "index.html",
        model=getattr(llm, "model", "MiniCPM5-2B"),
    )


@app.get("/study_cards/<path:filename>")
def study_card(filename: str):
    return send_from_directory(str(STUDY_CARDS_DIR), filename)


@app.get("/api/health")
def health():
    llm.ensure_started()
    return jsonify(llm.health())


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
