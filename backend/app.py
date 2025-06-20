import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# FLASK APP SETUP
app = Flask(__name__)
CORS(app) 

# GEMINI API SETUP
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash') 
    print("Gemini API configured successfully with gemini-2.5-flash.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    model = None

# DATABASE (JSON file)
DB_FILE = 'study_data.json'

def load_data():
    """Loads study data from the JSON file."""
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        return {'cards': []}
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    """Saves study data to the JSON file."""
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# API ROUTES

@app.route('/generate-cards', methods=['POST'])
def generate_cards():
    if not model:
        return jsonify({"error": "Gemini API not configured"}), 500

    data = request.get_json()
    topic = data.get('topic')
    num_cards = data.get('count', 10)

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    try:
        prompt = f"""
        Please act as a study assistant. Generate {num_cards} study items about the topic: "{topic}".
        The items should be a mix of simple flashcards and multiple-choice questions.
        Provide the output as a single, minified JSON array of objects. Do not include any text before or after the JSON array.
        Each object must have a "type" field ('flashcard' or 'mcq').
        For 'flashcard' type, the object should have "question" and "answer" fields.
        For 'mcq' type, the object should have a "question" field, an "options" field (an array of 4 strings), and a "correctAnswer" field (the string of the correct option).
        Example:
        [
          {{"type": "flashcard", "question": "What is the powerhouse of the cell?", "answer": "The Mitochondria"}},
          {{"type": "mcq", "question": "Which planet is known as the Red Planet?", "options": ["Earth", "Mars", "Jupiter", "Venus"], "correctAnswer": "Mars"}}
        ]
        """
        print(f"Sending prompt to Gemini for topic: {topic}")
        response = model.generate_content(prompt)
        
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        new_cards_data = json.loads(cleaned_response)

        study_data = load_data()
        existing_ids = {card.get('id', 0) for card in study_data['cards']}
        next_id = max(existing_ids) + 1 if existing_ids else 1
        
        today = datetime.datetime.utcnow().isoformat()

        for card in new_cards_data:
            card['id'] = next_id
            card['next_review_date'] = today
            card['interval'] = 1
            card['ease_factor'] = 2.5
            card['repetitions'] = 0
            study_data['cards'].append(card)
            next_id += 1
            
        save_data(study_data)
        return jsonify({"message": f"{len(new_cards_data)} cards generated successfully!", "cards": new_cards_data})

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Failed to generate or parse study cards from the API.", "details": str(e)}), 500

@app.route('/get-due-card', methods=['GET'])
def get_due_card():
    study_data = load_data()
    now_utc = datetime.datetime.utcnow()
    
    due_cards = [
        card for card in study_data['cards']
        if datetime.datetime.fromisoformat(card['next_review_date']) <= now_utc
    ]
    
    if not due_cards:
        return jsonify({"message": "No cards due for review. Great job!"})

    due_cards.sort(key=lambda x: x['next_review_date'])
    return jsonify(due_cards[0])

@app.route('/update-card-performance', methods=['POST'])
def update_card_performance():
    data = request.get_json()
    card_id = data.get('cardId')
    quality = data.get('quality') 

    if card_id is None or quality is None:
        return jsonify({"error": "cardId and quality are required"}), 400

    study_data = load_data()
    card_index = next((i for i, c in enumerate(study_data['cards']) if c['id'] == card_id), None)

    if card_index is None:
        return jsonify({"error": "Card not found"}), 404

    card = study_data['cards'][card_index]
    quality = int(quality)
    
    if quality < 2:
        card['repetitions'] = 0
        card['interval'] = 1
    else:
        card['repetitions'] += 1
        card['ease_factor'] = max(1.3, card['ease_factor'] + 0.1 - (3 - quality) * (0.08 + (3 - quality) * 0.02))
        if card['repetitions'] == 1:
            card['interval'] = 1
        elif card['repetitions'] == 2:
            card['interval'] = 6
        else:
            card['interval'] = round(card['interval'] * card['ease_factor'])

    delta = datetime.timedelta(days=card['interval'])
    card['next_review_date'] = (datetime.datetime.utcnow() + delta).isoformat()
    
    study_data['cards'][card_index] = card
    save_data(study_data)
    
    return jsonify({"message": "Card updated successfully", "updated_card": card})

# MAIN EXECUTION
if __name__ == '__main__':
    app.run(debug=True, port=5001)
