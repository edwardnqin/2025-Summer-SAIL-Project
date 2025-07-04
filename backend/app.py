import os
import json
import datetime
import pathlib
import re

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

# ─── 2) LIST FILES ─────────────────────────────────────────────────────
@app.get("/list-files")
def list_files():
    files = _load().get("files", [])
    return jsonify(files=[f["name"] for f in files])

# ─── 3) DELETE FILE ────────────────────────────────────────────────────
@app.post("/delete-file")
def delete_file():
    data = request.get_json(force=True)
    filename = data.get("filename")
    if not filename:
        return jsonify(error="No filename provided"), 400

    db = _load()
    before = len(db["files"])
    db["files"] = [f for f in db["files"] if f["name"] != filename]
    _save(db)

    after = len(db["files"])
    if before == after:
        return jsonify(error="File not found"), 404
    return jsonify(message=f"Deleted {filename}")

# ─── 4) SUMMARIZE ──────────────────────────────────────────────────────
@app.post("/summarize")
def summarize():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    if not selected_files:
        return jsonify(error="No files selected"), 400

    db_files = _load().get("files", [])
    files = [f for f in db_files if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404

    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = "Summarize the following material:\n\n" + merged

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

# ─── 5) ASK ────────────────────────────────────────────────────────────
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

# ─── 6) GENERATE FLASHCARDS ────────────────────────────────────────────
@app.post("/generate-cards")
def generate_cards():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    if not selected_files:
        return jsonify(error="No files selected"), 400

    db = _load()
    db_files = db.get("files", [])
    files = [f for f in db_files if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404

    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "You are a flashcard generator for spaced repetition learning.\n"
        "Extract flashcards from the following material. "
        "Return a JSON array of objects with 'question' and 'answer' fields.\n\n"
        + merged
    )

    try:
        response = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You generate flashcards in JSON."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.3
        )
        raw_text = response.choices[0].message.content.strip()

        # --- Robust JSON extraction ---
        match = re.search(r'(\[.*\])', raw_text, re.S)
        clean = match.group(1) if match else raw_text
        cards = json.loads(clean)

        # --- Append cards as before ---
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

# ─── 7) GET DUE CARD ───────────────────────────────────────────────────
@app.get("/get-due-card")
def get_due_card():
    now = datetime.datetime.utcnow()
    due = [c for c in _load().get("cards", [])
           if datetime.datetime.fromisoformat(c.get("next_review_date")) <= now]
    if not due:
        return jsonify(message="No cards due"), 200
    return jsonify(due[0])

# ─── 8) UPDATE CARD PERFORMANCE ────────────────────────────────────────
@app.post("/update-card-performance")
def update_performance():
    body = request.get_json(force=True)
    cid = body.get("cardId")
    q = int(body.get("quality", 0))

    db = _load()
    card = next((c for c in db.get("cards", []) if c.get("id") == cid), None)
    if not card:
        return jsonify(error="Card not found"), 404

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

# ─── 9) GENERATE QUIZ ───────────────────────────────────────────────────
@app.post("/generate-quiz")
def generate_quiz():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    if not selected_files:
        return jsonify(error="No files selected"), 400
    db_files = _load().get("files", [])
    files = [f for f in db_files if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404
    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "You are a quiz generator for a midterm exam. Based on the following material, "
        "create multiple-choice questions covering key concepts. "
        "Each question must have exactly four distinct options labeled A, B, C, and D. "
        "Return a JSON array of objects, each with 'question', 'options', and 'correctAnswer'.\n\n" + merged
    )
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You generate multiple-choice quizzes in JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    raw = response.choices[0].message.content.strip()
    match = re.search(r"(\[.*\])", raw, re.S)
    clean = match.group(1) if match else raw
    questions = json.loads(clean)
    return jsonify(questions=questions)

# ─── Run ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5001, debug=True)
