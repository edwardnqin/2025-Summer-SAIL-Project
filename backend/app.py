import os
import json
import datetime
import pathlib
import re
import random

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

# Automatically delete JSON DB on every server start
if os.path.exists(DB):
    os.remove(DB)
    print(f"{DB} deleted on server start.")

def _load():
    # If file doesn't exist, return a complete default structure
    if not os.path.exists(DB):
        return {
            "cards": [],
            "files": [],
            "summaries": [],
            "quizzes": []
        }

    # Load existing JSON file
    with open(DB) as f:
        data = json.load(f)

    # Ensure all required sections exist
    data.setdefault("cards", [])
    data.setdefault("files", [])
    data.setdefault("summaries", [])
    data.setdefault("quizzes", [])

    return data

def _save(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=4)

# ─── 1) UPLOAD ─────────────────────────────────────────────────────────
@app.post("/upload")
def upload():
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify(error="No files provided"), 400

    db = _load()
    added = 0

    for f in uploaded_files:
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
            continue  # skip unsupported files

        db["files"].append({"name": name, "text": text})
        added += 1

    _save(db)
    return jsonify(message=f"{added} files uploaded.", total_files=len(db["files"]))

# ─── 2) LIST FILES ─────────────────────────────────────────────────────
@app.get("/list-files")
def list_files():
    db = _load()
    file_names = [f["name"] for f in db.get("files", [])]
    unique_file_names = sorted(set(file_names))  # optional: sorted for consistent order
    return jsonify(files=unique_file_names)

# ─── 3) SUMMARIZE ──────────────────────────────────────────────────────
@app.post("/summarize")
def summarize():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    if not selected_files:
        return jsonify(error="No files selected"), 400

    # Load database to get the file texts
    db = _load()
    db_files = db.get("files", [])
    files = [f for f in db_files if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404

    # Merge the file texts
    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = "You are a study assistant helping students learn faster.\nSummarize the following material clearly and concisely:\n\n" + merged

    # Call OpenAI
    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful study assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    summary = response.choices[0].message.content.strip()

    # RE-LOAD the database to save the summary
    db = _load()
    if "summaries" not in db:
        db["summaries"] = []
    db["summaries"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "files": selected_files,
        "summary": summary
    })
    _save(db)

    return jsonify(summary=summary)

# ─── 4) ASK ────────────────────────────────────────────────────────────
@app.post("/ask")
def ask():
    data = request.get_json(force=True)
    query = data.get("query")
    if not query:
        return jsonify(error="No query"), 400

    # Load all study data
    db = _load()

    # Build context from files
    files_text = "\n\n".join(f["text"] for f in db.get("files", []))

    # Build context from summaries
    summaries_text = "\n\n".join(s["summary"] for s in db.get("summaries", []))

    # Build context from quizzes
    quizzes_text = "\n\n".join(
        "Q: " + q["question"] + "\n" +
        "\n".join([f"{letter}: {text}" for letter, text in q.get("options", {}).items()]) + "\n" +
        f"Correct Answer: {q.get('correctAnswer')}"
        for quiz in db.get("quizzes", [])
        for q in quiz.get("questions", [])
    )

    # Build context from flashcards
    flashcards_text = "\n\n".join(
        f"Q: {c.get('question')}\nA: {c.get('answer')}"
        for c in db.get("cards", [])
    )

    # Combine all contexts (truncate to ~950,000 chars if needed)
    context = "\n\n".join([files_text, summaries_text, quizzes_text, flashcards_text])[:950_000]

    # Build prompt for GPT
    prompt = (
        "You are a helpful tutor. Use the study material below to answer the student's question.\n\n"
        + context
        + "\n\nQuestion: "
        + query
    )

    # Call OpenAI
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

# ─── 5) GENERATE FLASHCARDS ────────────────────────────────────────────
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
        "Extract simple and clear flashcards from the following material, suitable for students to study."
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

# ─── 6) GET CARD ───────────────────────────────────────────────────
@app.get("/get-card")
def get_card():
    db = _load()
    cards = db.get("cards", [])
    if not cards:
        return jsonify(message="No cards available"), 404
    return jsonify(random.choice(cards))  # Pick a random card

# ─── 7) ANSWER CARD ───────────────────────────────────────────────────
@app.post("/answer-card")
def answer_card():
    data = request.get_json(force=True)
    card_id = data.get("cardId")
    correct = data.get("correct")

    if card_id is None or correct is None:
        return jsonify(error="Missing 'cardId' or 'correct'"), 400

    db = _load()
    cards = db.get("cards", [])

    # If correct, remove the card
    if correct:
        new_cards = [c for c in cards if c.get("id") != card_id]
        if len(new_cards) == len(cards):
            return jsonify(error="Card not found"), 404
        db["cards"] = new_cards
        _save(db)
        return jsonify(message=f"Card {card_id} removed.")
    else:
        # Incorrect answer, keep the card
        return jsonify(message="Card kept.")

# ─── 8) GENERATE QUIZ ───────────────────────────────────────────────────
@app.post("/generate-quiz")
def generate_quiz():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    if not selected_files:
        return jsonify(error="No files selected"), 400

    # Load the file texts
    db_files = _load().get("files", [])
    files = [f for f in db_files if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404

    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "You are a quiz generator for a midterm exam. Based on the following material, "
        "create clear multiple-choice questions covering key concepts that students should understand."
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

    # RE-LOAD database for saving
    db = _load()
    if "quizzes" not in db:
        db["quizzes"] = []
    db["quizzes"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "files": selected_files,
        "questions": questions
    })
    _save(db)

    return jsonify(questions=questions)

# ─── 9) DELETE FILE ─────────────────────────────────────────────────────
@app.post("/delete-file")
def delete_file():
    data = request.get_json(force=True)
    filename = data.get("filename")
    if not filename:
        return jsonify(error="Missing 'filename'"), 400

    db = _load()
    original_len = len(db["files"])
    db["files"] = [f for f in db["files"] if f["name"] != filename]
    removed_count = original_len - len(db["files"])
    _save(db)

    return jsonify(message=f"Removed {removed_count} entries with name '{filename}'.")

# ─── Run ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5001, debug=True)
