# Wisebud

Wisebud is a smart study assistant that helps students learn more efficiently by automatically generating study materials from their own notes and documents. Users can upload files, generate summaries, flashcards, and quizzes, and interact with their study content through natural language questions. Wisebud is designed for independent learners who want a simple, AI-powered study workflow.

## ✨ Features

### Core Learning Features

* **Smart Content Generation:** Upload TXT, PDF, DOCX, or image files to generate:

  * Concise summaries
  * Flashcards (Q\&A style)
  * Multiple-choice quizzes

* **Ask Your Study Materials:** Ask natural language questions, and Wisebud will find the answers in your uploaded files, summaries, quizzes, and flashcards.

* **Interactive Flashcards:** Practice flashcards directly in the app, and mark cards as correct or incorrect. Correct cards are removed from your study set.

* **Simple Data Storage:** All study content is saved locally in a `study_data.json` file.

* **Automatic Cleanup:** Summaries and quizzes are automatically cleared every 24 hours to keep your study content fresh.

## 🛠 Tech Stack

| Layer    | Technology                                             |
| -------- | ------------------------------------------------------ |
| Backend  | Python, Flask, Flask-CORS, OpenAI API, PyMuPDF, Pillow |
| Frontend | HTML, CSS, JavaScript (vanilla)                        |
| Storage  | Local JSON (`study_data.json`)                         |

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/ethanchang235/spaced-rep-study-assistant.git
cd spaced-rep-study-assistant
```

### 2. Set Up the Backend Environment

```bash
python -m venv venv
venv\Scripts\activate     # On Windows
# or
source venv/bin/activate  # On macOS/Linux

pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory and add your OpenAI API key:

```env
OPENAI_API_KEY="sk-your-api-key"
```

### 4. Run the Backend Server

```bash
python app.py
```

The backend will be available at:

```
http://localhost:5001
```

### 5. Run the Frontend (Optional)

If your frontend is a static website:

```bash
cd frontend
python -m http.server 8000
```

Visit:

```
http://localhost:8000
```

## 👨‍💻 Application Workflow

1. **Upload Files:** Upload TXT, PDF, DOCX, or image files as your study content.
2. **Generate Study Materials:** Click buttons in the frontend to generate:

   * Summaries
   * Flashcards
   * Quizzes
3. **Study:** Practice flashcards and answer quizzes in the app. Mark flashcards correct or incorrect.
4. **Ask Questions:** Type any question into the app to search your study data and get an AI-generated answer.
5. **Cleanup:** Summaries and quizzes are cleared from your database every 24 hours.

## 🔗 Backend API Endpoints

| Route             | Method | Purpose                                  |
| ----------------- | ------ | ---------------------------------------- |
| `/upload`         | POST   | Upload study materials                   |
| `/summarize`      | POST   | Generate summaries                       |
| `/generate-cards` | POST   | Generate flashcards                      |
| `/generate-quiz`  | POST   | Generate multiple-choice quizzes         |
| `/ask`            | POST   | Ask questions about your study materials |
| `/get-card`       | GET    | Get a random flashcard                   |
| `/answer-card`    | POST   | Mark a flashcard correct/incorrect       |

These are called automatically by the frontend's buttons and forms.

## 🔒 Security & Data

* All study data is stored **locally** in `study_data.json`.
* Your OpenAI API key is kept private in your `.env` file.

## 📈 Future Improvements

* Add spaced repetition algorithms for optimized review timing.
* Add user accounts and personal study profiles.
* Deploy the backend to a cloud platform.
* Improve frontend UI for a smoother user experience.
* Add study session tracking and statistics.

---

Wisebud is designed to be a simple, fast, and personal AI-powered study companion.
