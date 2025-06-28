import os, json, datetime, pathlib, tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from helpers import pdf_to_text, docx_to_text, image_to_base64

# ─── Gemini setup ──────────────────────────────────────────────────────
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

# ─── Flask app ─────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
CORS(app)

# ─── Simple JSON “DB” ──────────────────────────────────────────────────
DB = "study_data.json"
def _load():  return json.load(open(DB)) if os.path.exists(DB) else {"cards": [], "files": []}
def _save(d): json.dump(d, open(DB, "w"), indent=4)

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
        text = data.decode(errors="ignore")
    elif name.lower().endswith(".docx"):
        text = docx_to_text(data)
    elif name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
        text = image_to_base64(data)
    else:
        return jsonify(error="Unsupported type"), 415

    # persist file text
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
    prompt = "Summarize the key points of the following material:"
    rsp = model.generate_content(prompt + "\n\n" + merged)
    return jsonify(summary=rsp.text.strip())

# ─── 3) ASK (Q&A) ───────────────────────────────────────────────────────
@app.post("/ask")
def ask():
    q = request.json.get("query")
    if not q:
        return jsonify(error="No query"), 400
    ctx = "\n\n".join(f["text"] for f in _load()["files"])[:950_000]
    prompt = f"Answer as a helpful tutor using only this material:\n{ctx}\n\nQuestion: {q}"
    rsp = model.generate_content(prompt, generation_config={"temperature":0.3})
    return jsonify(answer=rsp.text.strip())

# ─── 4) GENERATE CARDS ───────────────────────────────────────────────────
@app.post("/generate-cards")
def generate_cards():
    db = _load()
    merged = "\n\n".join(f["text"] for f in db["files"])[:950_000]
    prompt = f"You are a spaced-repetition card writer. Return 10 JSON cards.\n\nTEXT:\n{merged}"
    rsp = model.generate_content(prompt)
    cards = json.loads(rsp.text.replace("```json","").replace("```","").strip())

    now = datetime.datetime.utcnow().isoformat()
    nxt = max([0] + [c["id"] for c in db["cards"]]) + 1
    for c in cards:
        c.update(id=nxt, next_review_date=now,
                 interval=1, ease_factor=2.5, repetitions=0)
        db["cards"].append(c)
        nxt += 1
    _save(db)
    return jsonify(message="Cards generated", cards=cards)

# ─── 5) GET DUE CARD ───────────────────────────────────────────────────
@app.get("/get-due-card")
def get_due_card():
    now = datetime.datetime.utcnow()
    due = [c for c in _load()["cards"]
           if datetime.datetime.fromisoformat(c["next_review_date"]) <= now]
    if not due:
        return jsonify(message="No cards due"), 200
    return jsonify(due[0])

# ─── 6) UPDATE PERFORMANCE ──────────────────────────────────────────────
@app.post("/update-card-performance")
def update_performance():
    body = request.get_json(force=True)
    cid, q = body.get("cardId"), int(body.get("quality",0))
    db = _load()
    card = next((c for c in db["cards"] if c["id"] == cid), None)
    if not card:
        return jsonify(error="Card not found"), 404

    # SM-2 algorithm
    if q < 2:
        card.update(repetitions=0, interval=1)
    else:
        card["repetitions"] += 1
        ef = card["ease_factor"] + 0.1 - (3 - q)*(0.08 + (3 - q)*0.02)
        card["ease_factor"] = max(1.3, ef)
        card["interval"] = (1 if card["repetitions"]==1 else
                            6 if card["repetitions"]==2 else
                            round(card["interval"] * card["ease_factor"]))
    card["next_review_date"] = (datetime.datetime.utcnow() +
        datetime.timedelta(days=card["interval"])).isoformat()
    _save(db)
    return jsonify(card)

# ─── Run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(port=5001, debug=True)
