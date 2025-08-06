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

from helpers import pdf_to_text, docx_to_text, image_to_base64, _load_users, _save_users, _hash_password

# ─── OpenAI setup ──────────────────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
# Use "gpt-4o" as the default model but allow override via env variable
MODEL = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o")

# ─── Flask app ─────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
CORS(app)

# ─── Simple JSON "DB" ──────────────────────────────────────────────────
DB = "study_data.json"

def _load(username=None):
    if not os.path.exists(DB):
        data = {}
    else:
        with open(DB) as f:
            data = json.load(f)
    if username:
        if username not in data:
            data[username] = {
                "files": {},
                "cards": {},
                "todos": [],
                "summaries": [],
                "quizzes": []
            }
        return data, data[username]

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
    username = request.headers.get("Username")
    if not uploaded_files or not course or not username:
        return jsonify(error="Missing files, course, or username"), 400

    data, db = _load(username)
    _ensure_course_section(db, "files", course)
    added = 0

    for f in uploaded_files:
        name = pathlib.Path(f.filename).name
        data_bytes = f.read()

        if name.lower().endswith(".pdf"):
            text = pdf_to_text(data_bytes)
        elif name.lower().endswith((".txt", ".md")):
            text = data_bytes.decode("utf-8", errors="ignore")
        elif name.lower().endswith(".docx"):
            text = docx_to_text(data_bytes)
        elif name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
            text = image_to_base64(data_bytes)
        else:
            continue

        db["files"][course].append({ "name": name, "text": text })
        added += 1

    _save(data)
    return jsonify(message=f"{added} files uploaded.", total_files=len(db["files"][course]))


# ─── 2) LIST FILES ─────────────────────────────────────────────────────
@app.get("/list-files")
def list_files():
    course = request.args.get("course")
    username = request.headers.get("Username")
    if not course or not username:
        return jsonify(error="Missing course or username"), 400

    data, db = _load(username)
    if course not in db["files"]:
        return jsonify(files=[])
    file_names = [f["name"] for f in db["files"][course]]
    return jsonify(files=sorted(set(file_names)))

# ─── 3) DELETE FILE ─────────────────────────────────────────────────────
@app.post("/delete-file")
def delete_file():
    data = request.get_json(force=True)
    course = data.get("course")
    filename = data.get("filename")
    username = request.headers.get("Username")

    if not course or not filename or not username:
        return jsonify(error="Missing 'course', 'filename', or 'username'"), 400

    all_data, db = _load(username)
    if course not in db["files"]:
        return jsonify(message="Course not found."), 404
    original_len = len(db["files"][course])
    db["files"][course] = [f for f in db["files"][course] if f["name"] != filename]
    removed_count = original_len - len(db["files"][course])

    _save(all_data)
    return jsonify(message=f"Removed {removed_count} entries with name '{filename}'.")

# ─── 4) SUMMARIZE ──────────────────────────────────────────────────────
@app.post("/summarize")
def summarize():
    data = request.get_json(force=True)
    selected = data.get("filenames", [])
    course = data.get("course")
    username = request.headers.get("Username")
    if not selected or not course or not username:
        return jsonify(error="Missing files, course, or username"), 400

    # Read optional model override and instructions
    req_model = (data.get("model") or "").strip()
    model_to_use = req_model if req_model else MODEL
    instructions = (data.get("instructions") or "").strip()

    all_data, db = _load(username)
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

    # Build a system prompt, appending any user-provided instructions
    system_prompt = "You are a helpful study assistant."
    if instructions:
        system_prompt += "\n" + instructions
    response = openai.chat.completions.create(
        model=model_to_use,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=1,
    )

    summary = response.choices[0].message.content.strip()
    db["summaries"].append({ "course": course, "summary": summary })
    _save(all_data)
    return jsonify(summary=summary)

# ─── 5) GENERATE FLASHCARDS ────────────────────────────────────────────
@app.post("/generate-cards")
def generate_cards():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    course = data.get("course")
    username = request.headers.get("Username")
    if not selected_files or not course or not username:
        return jsonify(error="Missing files, course, or username"), 400
    
    req_model = (data.get("model") or "").strip()
    model_to_use = req_model if req_model else MODEL
    instructions = (data.get("instructions") or "").strip()

    all_data, db = _load(username)
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

    system_prompt = "You generate flashcards in JSON."
    if instructions:
        system_prompt += "\n" + instructions
    response = openai.chat.completions.create(
        model=model_to_use,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt}
        ],
        temperature=1,
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

    _save(all_data)
    return jsonify(message=f"{len(cards)} cards generated.", cards=cards)

# ─── 6) GET CARD ───────────────────────────────────────────────────────
@app.get("/get-card")
def get_card():
    course = request.args.get("course")
    username = request.headers.get("Username")
    if not course or not username:
        return jsonify(error="Missing course or username"), 400

    all_data, db = _load(username)
    cards = db["cards"].get(course)
    if not cards:
        return jsonify(message="No cards available"), 404

    now = datetime.datetime.now()
    due_cards = [c for c in cards if datetime.datetime.fromisoformat(c["next_review"]) <= now]

    if due_cards:
        next_card = min(due_cards, key=lambda c: datetime.datetime.fromisoformat(c["next_review"]))
    else:
        next_card = min(cards, key=lambda c: datetime.datetime.fromisoformat(c["next_review"]))

    next_card.setdefault("type", "basic")
    return jsonify(next_card)



# ─── 7) ANSWER CARD ────────────────────────────────────────────────────
@app.post("/answer-card")
def answer_card():
    data = request.get_json(force=True)
    course = data.get("course")
    card_id = data.get("cardId")
    username = request.headers.get("Username")

    # Support both 'quality' (preferred) and 'correct' (legacy) inputs
    quality = data.get("quality")
    if quality is None:
        correct = data.get("correct")
        if correct is None:
            return jsonify(error="Missing 'quality' or 'correct'"), 400
        # map boolean correct/incorrect to a 0–5 quality score
        quality = 5 if correct else 2

    if course is None or card_id is None or username is None:
        return jsonify(error="Missing 'course', 'cardId', or 'username'"), 400

    all_data, db = _load(username)
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

    _save(all_data)
    return jsonify(message="Card updated.")


# ─── 8) GENERATE QUIZ ──────────────────────────────────────────────────
@app.post("/generate-quiz")
def generate_quiz():
    data = request.get_json(force=True)
    selected_files = data.get("filenames", [])
    course = data.get("course")
    username = request.headers.get("Username")
    if not selected_files or not course or not username:
        return jsonify(error="Missing files, course, or username"), 400
    
    # Read optional model override and instructions
    req_model = (data.get("model") or "").strip()
    model_to_use = req_model if req_model else MODEL
    instructions = (data.get("instructions") or "").strip()
    
    all_data, db = _load(username)
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

    # Build system prompt with optional instructions
    system_prompt = "You generate multiple-choice quizzes in JSON."
    if instructions:
        system_prompt += "\n" + instructions
    response = openai.chat.completions.create(
        model=model_to_use,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=1
    )

    raw = response.choices[0].message.content.strip()
    match = re.search(r"(\[.*\])", raw, re.S)
    clean = match.group(1) if match else raw
    questions = json.loads(clean)

    db["quizzes"].append({
        "timestamp": datetime.datetime.now().isoformat(),
        "course": course,
        "files": selected_files,
        "questions": questions
    })
    _save(all_data)

    return jsonify(questions=questions)

# ─── 9) LIST TODOS ─────────────────────────────────────────────────────
@app.get("/list-todos")
def list_todos():
    username = request.headers.get("Username")
    if not username:
        return jsonify(error="Missing username"), 401

    _, db = _load(username)
    return jsonify(todos=db.get("todos", []))

# ─── 10) ADD TODO ──────────────────────────────────────────────────────
@app.post("/add-todo")
def add_todo():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    username = request.headers.get("Username")
    if not text or not username:
        return jsonify(error="Missing text or username"), 400

    all_data, db = _load(username)
    if text in db.get("todos", []):
        return jsonify(message="Todo already exists."), 200

    db.setdefault("todos", []).append(text)
    _save(all_data)
    return jsonify(message="Todo added.", todos=db["todos"])

# ─── 11) REMOVE TODO ───────────────────────────────────────────────────
@app.post("/remove-todo")
def remove_todo():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    username = request.headers.get("Username")
    if not text or not username:
        return jsonify(error="Missing text or username"), 400

    all_data, db = _load(username)
    if text not in db.get("todos", []):
        return jsonify(error="Todo not found."), 404

    db["todos"] = [t for t in db["todos"] if t != text]
    _save(all_data)
    return jsonify(message="Todo removed.", todos=db["todos"])

# ─── 12) ASK ────────────────────────────────────────────────────────────
@app.post("/ask")
def ask():
    data = request.get_json(force=True)
    query = data.get("query")
    course = data.get("course")
    username = request.headers.get("Username")


    if not query or not course or not username:
        return jsonify(error="Missing 'query', 'course', or 'username'"), 400

    all_data, db = _load(username)

    # Course-specific context
    files_text = "\n\n".join(f["text"] for f in db.get("files", {}).get(course, []))
    summaries_text = "\n\n".join(s["summary"] for s in db.get("summaries", []) if s.get("course") == course)
    quizzes_text = "\n\n".join(
        "Q: " + q["question"] + "\n" +
        "\n".join([f"{letter}: {text}" for letter, text in q.get("options", {}).items()]) + "\n" +
        f"Correct Answer: {q.get('correctAnswer')}"
        for quiz in db.get("quizzes", [])
        if quiz.get("course") == course
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

@app.post("/register")
def register():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify(error="Missing username or password"), 400
    if not (8 <= len(password) <= 16):
        return jsonify(error="Password must be 8–16 characters"), 400
    if not any(c.islower() for c in password) or not any(c.isupper() for c in password):
        return jsonify(error="Password must include both lowercase and uppercase letters"), 400
    if not any(c.isdigit() for c in password):
        return jsonify(error="Password must include a number"), 400
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for c in password):
        return jsonify(error="Password must include a special character"), 400

    users = _load_users()
    if username in users:
        return jsonify(error="Username already exists"), 400

    users[username] = { "password": _hash_password(password) }
    _save_users(users)

    return jsonify(message="User registered successfully")


@app.post("/login")
def login():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify(error="Missing username or password"), 400

    users = _load_users()
    hashed = _hash_password(password)

    if username not in users or users[username]["password"] != hashed:
        return jsonify(error="Invalid username or password"), 401

    return jsonify(message="Login successful")


# ─── Run ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5001, debug=True)
