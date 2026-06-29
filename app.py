import os
import json
import uuid
import re
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
LOG_FILE = "audit_log.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def write_log(entry):
    logs = read_log()
    logs.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)


def llm_signal(text):
    try:
        prompt = f"""
You are an AI content detector. Return only one number from 0.0 to 1.0.
0.0 means definitely human-written.
1.0 means definitely AI-generated.

Text:
{text}
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        output = response.choices[0].message.content.strip()
        match = re.search(r"0?\.\d+|1\.0|1|0", output)
        if match:
            return max(0.0, min(1.0, float(match.group())))
    except Exception:
        pass

    return 0.5


def stylometric_signal(text):
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"\b\w+\b", text.lower())

    if len(words) < 10 or len(sentences) == 0:
        return 0.5

    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
    avg_len = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((x - avg_len) ** 2 for x in sentence_lengths) / len(sentence_lengths)

    vocabulary_diversity = len(set(words)) / len(words)
    punctuation_density = len(re.findall(r"[,;:!?-]", text)) / max(len(words), 1)

    uniformity_score = max(0.0, min(1.0, 1 - (variance / 50)))
    vocab_score = max(0.0, min(1.0, 1 - vocabulary_diversity))
    punctuation_score = max(0.0, min(1.0, 1 - punctuation_density))

    return round((uniformity_score * 0.5) + (vocab_score * 0.3) + (punctuation_score * 0.2), 2)


def combine_scores(llm_score, style_score):
    return round((llm_score * 0.6) + (style_score * 0.4), 2)


def get_attribution(score):
    if score >= 0.80:
        return "likely_ai"
    elif score <= 0.39:
        return "likely_human"
    return "uncertain"


def get_label(attribution):
    if attribution == "likely_ai":
        return "Likely AI-generated. Our system has high confidence that this content may have been generated using AI. Because AI detection can be imperfect, creators may appeal this decision."
    if attribution == "likely_human":
        return "Likely human-written. Our system has high confidence that this content appears to have been written by a human."
    return "Uncertain. The system could not confidently determine whether this content is AI-generated or human-written. No strong attribution claim should be made."


@app.route("/")
def home():
    return jsonify({"message": "Provenance Guard API is running"})


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json()

    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Missing required fields: text and creator_id"}), 400

    text = data["text"]
    creator_id = data["creator_id"]
    content_id = str(uuid.uuid4())

    llm_score = llm_signal(text)
    style_score = stylometric_signal(text)
    confidence = combine_scores(llm_score, style_score)
    attribution = get_attribution(confidence)
    label = get_label(attribution)

    entry = {
        "event": "classification",
        "timestamp": now_iso(),
        "content_id": content_id,
        "creator_id": creator_id,
        "text_preview": text[:120],
        "llm_score": llm_score,
        "style_score": style_score,
        "confidence": confidence,
        "attribution": attribution,
        "label": label,
        "status": "classified",
    }

    write_log(entry)

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
        "status": "classified",
        "signals": {
            "llm_score": llm_score,
            "style_score": style_score,
        }
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json()

    if not data or "content_id" not in data or "creator_reasoning" not in data:
        return jsonify({"error": "Missing required fields: content_id and creator_reasoning"}), 400

    content_id = data["content_id"]
    creator_reasoning = data["creator_reasoning"]

    logs = read_log()
    original = None

    for entry in logs:
        if entry.get("content_id") == content_id and entry.get("event") == "classification":
            original = entry
            entry["status"] = "under_review"

    if original is None:
        return jsonify({"error": "content_id not found"}), 404

    appeal_entry = {
        "event": "appeal",
        "timestamp": now_iso(),
        "content_id": content_id,
        "creator_id": original.get("creator_id"),
        "creator_reasoning": creator_reasoning,
        "original_attribution": original.get("attribution"),
        "original_confidence": original.get("confidence"),
        "status": "under_review",
    }

    logs.append(appeal_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

    return jsonify({
        "message": "Appeal received",
        "content_id": content_id,
        "status": "under_review"
    })


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": read_log()[-20:]})


if __name__ == "__main__":
    app.run(debug=True)