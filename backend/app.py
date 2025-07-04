import os
import json
import datetime
import pathlib

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import openai

from helpers import pdf_to_text, docx_to_text, image_to_base64

# ─── OpenAI setup ──────────────────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

# ─── Flask app ─────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
CORS(app)

# ─── Simple JSON "DB" ──────────────────────────────────────────────────
DB = "study_data.json"
def _load():
    return json.load(open(DB)) if os.path.exists(DB) else {"cards": [], "files": []}

def _save(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=4)

# ─── 1) UPLOAD ─────────────────────────────────────────────────────────
@app.post("/upload")
def upload():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file"), 400

    name = pathlib.Path(f.filename).name
    data = f.read()

    if name.lower().endswith(".pdf"):
        text = pdf_to_text(data)
    elif name.lower().endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
    elif name.lower().endswith(".docx"):
        text = docx_to_text(data)
    elif name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
        text = image_to_base64(data)
    else:
        return jsonify(error="Unsupported file type"), 415

    db = _load()
    db["files"].append({"name": name, "text": text})
    _save(db)
    return jsonify(message=f"{name} uploaded.", total_files=len(db["files"]))

# ─── 2) SUMMARIZE ───────────────────────────────────────────────────────
@app.get("/summarize")
def summarize():
    files = _load()["files"]
    if not files:
        return jsonify(error="No files"), 400

    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "Summarize the following material:\n\n" + merged
    )

    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful study assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    summary = response.choices[0].message.content.strip()
    return jsonify(summary=summary)

# ─── 3) ASK (Q&A) ───────────────────────────────────────────────────────
@app.post("/ask")
def ask():
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify(error="No query"), 400

    ctx = "\n\n".join(f["text"] for f in _load()["files"])[:950_000]
    prompt = (
        "You are a helpful tutor. Use only the material below to answer the question.\n\n"
        + ctx
        + "\n\nQuestion: "
        + query
    )

    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful tutor."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    answer = response.choices[0].message.content.strip()
    return jsonify(answer=answer)

# ─── 4) GENERATE FLASHCARDS ─────────────────────────────────────────────
@app.post("/generate-cards")
def generate_cards():
    db = _load()
    merged = "\n\n".join(f["text"] for f in db["files"])[:950_000]

    # New clearer prompt
    prompt = (
        "You are a flashcard generator for spaced repetition learning.\n"
        "Extract all possible flashcards from the following material. "
        "For each flashcard, return a JSON object with two fields: 'question' and 'answer'.\n"
        "Return your response as a single JSON array of these objects, no explanations, just valid JSON.\n"
        "Material:\n"
        f"{merged}"
    )

    try:
        # Call OpenAI with updated syntax
        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You generate flashcards in JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        # Get the text from the response
        raw_text = response.choices[0].message.content.strip()

        # Strip code block markers if they exist
        if raw_text.startswith("```json"):
            raw_text = raw_text.removeprefix("```json").removesuffix("```").strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.removeprefix("```").removesuffix("```").strip()

        # Parse the JSON output
        cards = json.loads(raw_text)

        # Add spaced-repetition fields to each card
        now = datetime.datetime.utcnow().isoformat()
        next_id = max([0] + [c.get("id", 0) for c in db.get("cards", [])]) + 1
        for c in cards:
            c.update(
                id=next_id,
                next_review_date=now,
                interval=1,
                ease_factor=2.5,
                repetitions=0
            )
            db["cards"].append(c)
            next_id += 1

        _save(db)
        return jsonify(message=f"{len(cards)} cards generated.", cards=cards)

    except json.JSONDecodeError:
        return jsonify(error="Failed to parse OpenAI response as JSON."), 500

    except Exception as e:
        return jsonify(error=str(e)), 500

# ─── 5) GET DUE FLASHCARD ───────────────────────────────────────────────
@app.get("/get-due-card")
def get_due_card():
    now = datetime.datetime.utcnow()
    due = [c for c in _load().get("cards", [])
           if datetime.datetime.fromisoformat(c.get("next_review_date")) <= now]
    if not due:
        return jsonify(message="No cards due"), 200
    return jsonify(due[0])

# ─── 6) UPDATE CARD PERFORMANCE ─────────────────────────────────────────
@app.post("/update-card-performance")
def update_performance():
    body = request.get_json(force=True)
    cid = body.get("cardId")
    q = int(body.get("quality", 0))

    db = _load()
    card = next((c for c in db.get("cards", []) if c.get("id") == cid), None)
    if not card:
        return jsonify(error="Card not found"), 404

    # SM-2 algorithm
    if q < 2:
        card.update(repetitions=0, interval=1)
    else:
        card["repetitions"] += 1
        ef = card["ease_factor"] + 0.1 - (3 - q) * (0.08 + (3 - q) * 0.02)
        card["ease_factor"] = max(1.3, ef)
        card["interval"] = (1 if card["repetitions"] == 1 else
                            6 if card["repetitions"] == 2 else
                            round(card["interval"] * card["ease_factor"]))
    card["next_review_date"] = (datetime.datetime.utcnow() +
        datetime.timedelta(days=card["interval"])).isoformat()
    _save(db)
    return jsonify(card)

# ─── Run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5001, debug=True)
