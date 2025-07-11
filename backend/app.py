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

    # Merge the selected file texts
    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "You are a flashcard generator for spaced repetition learning.\n"
        "Extract flashcards from the following material. "
        "Return a JSON array of objects with 'question' and 'answer' fields.\n\n"
        + merged
    )

    # Send request to OpenAI
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You generate flashcards in JSON."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.3
    )
    raw_text = response.choices[0].message.content.strip()

    # Extract JSON from response
    match = re.search(r'(\[.*\])', raw_text, re.S)
    clean = match.group(1) if match else raw_text
    cards = json.loads(clean)

    # Assign an ID to each card and save
    next_id = max([0] + [c.get("id", 0) for c in db.get("cards", [])]) + 1
    for c in cards:
        c.update(id=next_id)
        db["cards"].append(c)
        next_id += 1

    _save(db)
    return jsonify(message=f"{len(cards)} cards generated.", cards=cards)

# ─── 7) GENERATE QUIZ ───────────────────────────────────────────────────
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
