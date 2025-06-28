import os, json, datetime, fitz
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai          # Gemini SDK

# configuration
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
CORS(app)

DB = "study_data.json"
def _load():  return json.load(open(DB)) if os.path.exists(DB) else {"cards": []}
def _save(d): json.dump(d, open(DB, "w"), indent=4)

# routes
@app.post("/generate-cards")
def generate_cards():
    text = request.form.get("text_content", "")
    if not text and "file" in request.files:
        pdf = fitz.open(stream=request.files["file"].read(), filetype="pdf")
        text = "".join(p.get_text() for p in pdf)
    if not text.strip():
        return jsonify(error="No content"), 400

    n = int(request.form.get("count", 10))
    prompt = f"You are a spaced-repetition card writer. Return {n} JSON cards."
    rsp = model.generate_content(prompt + "\n\nTEXT:\n" + text[:12000])
    cards = json.loads(rsp.text.replace("```json", "")
                               .replace("```", "")
                               .strip())

    data, nxt = _load(), max([0, *[c["id"] for c in _load()["cards"]]]) + 1
    now = datetime.datetime.utcnow().isoformat()
    for c in cards:
        c.update(id=nxt, next_review_date=now,
                 interval=1, ease_factor=2.5, repetitions=0)
        data["cards"].append(c); nxt += 1
    _save(data); return jsonify(cards=cards)

@app.get("/get-due-card")
def get_due_card():
    now = datetime.datetime.utcnow()
    due = [c for c in _load()["cards"]
           if datetime.datetime.fromisoformat(c["next_review_date"]) <= now]
    return jsonify(card=due[0] if due else None)

@app.post("/update-card-performance")
def update_card():
    body = request.get_json(force=True)
    cid, q = body["cardId"], int(body["quality"])
    data = _load()
    card = next((c for c in data["cards"] if c["id"] == cid), None)
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
    _save(data); return jsonify(card=card)

if __name__ == "__main__":
    app.run(port=5001, debug=True)
