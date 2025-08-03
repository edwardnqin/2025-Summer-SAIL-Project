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

def _load():
    if not os.path.exists(DB):
        return {
            "files": {},
            "cards": {},
            "summaries": [],
            "quizzes": [],
            "todos": []
        }
    with open(DB) as f:
        data = json.load(f)
    data.setdefault("files", {})
    data.setdefault("cards", {})
    data.setdefault("summaries", [])
    data.setdefault("quizzes", [])
    data.setdefault("todos", [])
    return data

def _save(data):
    with open(DB, "w") as f:
        json.dump(data, f, indent=4)

def _ensure_course_section(db, section, course):
    if course not in db[section]:
        db[section][course] = []

# ─── 1) UPLOAD ─────────────────────────────────────────────────────────
@app.post("/upload")
def upload():
    uploaded_files = request.files.getlist("files")
    course = request.form.get("course")
    if not uploaded_files or not course:
        return jsonify(error="Missing files or course name"), 400

    db = _load()
    _ensure_course_section(db, "files", course)
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
            continue

        db["files"][course].append({"name": name, "text": text})
        added += 1

    _save(db)
    return jsonify(message=f"{added} files uploaded.", total_files=len(db["files"][course]))

# ─── 2) LIST FILES ─────────────────────────────────────────────────────
@app.get("/list-files")
def list_files():
    course = request.args.get("course")
    db = _load()
    if not course or course not in db["files"]:
        return jsonify(files=[])
    file_names = [f["name"] for f in db["files"][course]]
    return jsonify(files=sorted(set(file_names)))

# ─── 3) DELETE FILE ─────────────────────────────────────────────────────
@app.post("/delete-file")
def delete_file():
    data = request.get_json(force=True)
    course = data.get("course")
    filename = data.get("filename")
    if not course or not filename:
        return jsonify(error="Missing 'course' or 'filename'"), 400

    db = _load()
    if course not in db["files"]:
        return jsonify(message="Course not found."), 404
    original_len = len(db["files"][course])
    db["files"][course] = [f for f in db["files"][course] if f["name"] != filename]
    removed_count = original_len - len(db["files"][course])
    _save(db)
    return jsonify(message=f"Removed {removed_count} entries with name '{filename}'.")

# ─── 4) SUMMARIZE ──────────────────────────────────────────────────────
@app.post("/summarize")
def summarize():
    data = request.get_json(force=True)
    selected = data.get("filenames", [])
    course = data.get("course")
    if not selected or not course:
        return jsonify(error="Missing files or course name"), 400

    db = _load()
    _ensure_course_section(db, "files", course)
    files = [f for f in db["files"][course] if f["name"] in selected]
    if not files:
        return jsonify(error="No matching files"), 404

    prompt_parts = []
    for i, f in enumerate(files, start=1):
        prompt_parts.append(f"---\nDOCUMENT #{i} FILENAME: {f['name']}\n\n{f['text']}\n")

    prompt = (
        "You are a study assistant. For each document below, first invent a clear, concise title based on its content, "
        "then write a brief summary. Format **exactly** like this:\n\n"
        "**<Title for Document 1>**\nSummary of Document 1...\n\n"
        "**<Title for Document 2>**\nSummary of Document 2...\n\n"
        + "\n".join(prompt_parts)
    )

    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful study assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    summary = response.choices[0].message.content.strip()
    return jsonify(summary=summary)

# ─── 5) GENERATE FLASHCARDS ────────────────────────────────────────────
@app.post("/generate-cards")
def generate_cards():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    course = data.get("course")
    if not selected_files or not course:
        return jsonify(error="Missing files or course name"), 400

    db = _load()
    _ensure_course_section(db, "files", course)
    _ensure_course_section(db, "cards", course)
    files = [f for f in db["files"][course] if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404

    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "You are a flashcard generator for spaced repetition learning.\n"
        "Extract simple and clear flashcards from the following material, suitable for students to study."
        "Return a JSON array of objects with 'question' and 'answer' fields.\n\n"
        + merged
    )

    response = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You generate flashcards in JSON."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.3
    )
    raw_text = response.choices[0].message.content.strip()
    match = re.search(r'(\[.*\])', raw_text, re.S)
    clean = match.group(1) if match else raw_text
    cards = json.loads(clean)

    next_id = max([0] + [c.get("id", 0) for c in db["cards"][course]]) + 1
    for c in cards:
        c.update(
            id=next_id,
            review_count=0,
            interval=1,
            ease_factor=2.5,
            next_review=datetime.datetime.now().isoformat()
        )
        db["cards"][course].append(c)
        next_id += 1

    _save(db)
    return jsonify(message=f"{len(cards)} cards generated.", cards=cards)

# ─── 6) GET CARD ───────────────────────────────────────────────────────
@app.get("/get-card")
def get_card():
    course = request.args.get("course")
    if not course:
        return jsonify(error="Missing course name"), 400

    db = _load()
    cards = db["cards"].get(course)
    if not cards:
        return jsonify(message="No cards available"), 404

    now = datetime.datetime.now()
    # cards that are due right now or in the past
    due_cards = [c for c in cards if datetime.datetime.fromisoformat(c["next_review"]) <= now]

    if due_cards:
        # pick the due card with the earliest next_review
        next_card = min(due_cards, key=lambda c: datetime.datetime.fromisoformat(c["next_review"]))
    else:
        # if nothing is due, pick the card with the soonest upcoming next_review
        next_card = min(cards, key=lambda c: datetime.datetime.fromisoformat(c["next_review"]))

    return jsonify(next_card)


# ─── 7) ANSWER CARD ────────────────────────────────────────────────────
@app.post("/answer-card")
def answer_card():
    data = request.get_json(force=True)
    course = data.get("course")
    card_id = data.get("cardId")

    # Support both 'quality' (preferred) and 'correct' (legacy) inputs
    quality = data.get("quality")
    if quality is None:
        correct = data.get("correct")
        if correct is None:
            return jsonify(error="Missing 'quality' or 'correct'"), 400
        # map boolean correct/incorrect to a 0–5 quality score
        quality = 5 if correct else 2

    if course is None or card_id is None:
        return jsonify(error="Missing 'course' or 'cardId'"), 400

    db = _load()
    cards = db["cards"].get(course)
    if not cards:
        return jsonify(error="Course not found"), 404

    card = next((c for c in cards if c.get("id") == card_id), None)
    if card is None:
        return jsonify(error="Card not found"), 404

    # Apply a simple SM‑2 style update
    if quality < 3:
        # low quality: reset the review count and interval
        card["review_count"] = 0
        card["interval"] = 1
    else:
        card["review_count"] += 1
        # Update ease factor (SM‑2 formula with lower bound 1.3)
        new_ef = card["ease_factor"] + (
            0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        )
        card["ease_factor"] = max(1.3, new_ef)
        # Set interval depending on review count
        if card["review_count"] == 1:
            card["interval"] = 1
        elif card["review_count"] == 2:
            card["interval"] = 6
        else:
            card["interval"] = round(card["interval"] * card["ease_factor"])

    # Schedule next review date
    card["next_review"] = (
        datetime.datetime.now() + datetime.timedelta(days=card["interval"])
    ).isoformat()

    _save(db)
    return jsonify(message="Card updated.")


# ─── 8) GENERATE QUIZ ──────────────────────────────────────────────────
@app.post("/generate-quiz")
def generate_quiz():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    course = data.get("course")
    if not selected_files or not course:
        return jsonify(error="Missing files or course name"), 400

    db = _load()
    _ensure_course_section(db, "files", course)
    files = [f for f in db["files"][course] if f["name"] in selected_files]
    if not files:
        return jsonify(error="No matching files found"), 404

    merged = "\n\n".join(f["text"] for f in files)[:950_000]
    prompt = (
        "You are a quiz generator for a midterm exam. Based on the following material, "
        "generate **exactly 10** clear multiple-choice questions that cover important concepts students should know. "
        "Each question must have exactly four distinct answer options labeled A, B, C, and D. "
        "Clearly indicate the correct answer using a 'correctAnswer' field. "
        "Return the result as a valid JSON array of 10 objects. "
        "Each object must contain a 'question', an 'options' dictionary with keys A/B/C/D, and a 'correctAnswer' key.\n\n"
        + merged
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

    db["quizzes"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "files": selected_files,
        "questions": questions
    })
    _save(db)

    return jsonify(questions=questions)

# ─── 9) LIST TODOS ─────────────────────────────────────────────────────
@app.get("/list-todos")
def list_todos():
    db = _load()
    return jsonify(todos=db["todos"])

# ─── 10) ADD TODO ──────────────────────────────────────────────────────
@app.post("/add-todo")
def add_todo():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify(error="Missing or empty 'text'"), 400

    db = _load()
    if text in db["todos"]:
        return jsonify(message="Todo already exists."), 200

    db["todos"].append(text)
    _save(db)
    return jsonify(message="Todo added.", todos=db["todos"])

# ─── 11) REMOVE TODO ───────────────────────────────────────────────────
@app.post("/remove-todo")
def remove_todo():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify(error="Missing or empty 'text'"), 400

    db = _load()
    if text not in db["todos"]:
        return jsonify(error="Todo not found."), 404

    db["todos"] = [t for t in db["todos"] if t != text]
    _save(db)
    return jsonify(message="Todo removed.", todos=db["todos"])

# ─── 12) ASK ────────────────────────────────────────────────────────────
@app.post("/ask")
def ask():
    data = request.get_json(force=True)
    query = data.get("query")
    course = data.get("course")

    if not query:
        return jsonify(error="Missing 'query'"), 400
    if not course:
        return jsonify(error="Missing 'course'"), 400

    db = _load()

    # Course-specific context
    files_text = "\n\n".join(f["text"] for f in db.get("files", {}).get(course, []))
    summaries_text = "\n\n".join(s["summary"] for s in db.get("summaries", []) if s.get("course") == course)
    quizzes_text = "\n\n".join(
        "Q: " + q["question"] + "\n" +
        "\n".join([f"{letter}: {text}" for letter, text in q.get("options", {}).items()]) + "\n" +
        f"Correct Answer: {q.get('correctAnswer')}"
        for quiz in db.get("quizzes", [])
        if course in quiz.get("files", [])
        for q in quiz.get("questions", [])
    )
    flashcards_text = "\n\n".join(
        f"Q: {c.get('question')}\nA: {c.get('answer')}"
        for c in db.get("cards", {}).get(course, [])
    )

    # Combine context
    context = "\n\n".join([files_text, summaries_text, quizzes_text, flashcards_text])[:950_000]

    prompt = (
        "You are a helpful tutor. Use the study material below to answer the student's question.\n\n"
        + context
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


# ─── Run ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5001, debug=True)
