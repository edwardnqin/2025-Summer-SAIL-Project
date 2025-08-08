# Wisebud — 2025 Summer SAIL Project

Wisebud is a smart AI-powered study assistant that helps students learn more efficiently by generating summaries, flashcards, quizzes, and answering questions based on uploaded notes. Designed for independent learners and optimized with spaced repetition, Wisebud streamlines your study workflow across multiple courses and users.

GitHub repo: https://github.com/edwardnqin/2025-Summer-SAIL-Project.git

---

## ✨ Features

### Core Learning Tools

- 📄 **Upload Files:** Supports `.txt`, `.pdf`, `.docx`, and images.
- 🧠 **Summarize Notes:** Auto-generate titled summaries using GPT.
- 🃏 **Generate Flashcards:** JSON-based flashcards with spaced repetition scheduling (SM‑2).
- ❓ **Ask Questions:** Ask natural language questions using all uploaded + generated content.
- 📝 **Generate Quizzes:** Auto-create 10 multiple-choice questions per session.

### Study Flow & Memory Boost

- ⏱ **Spaced Repetition:** Flashcards track review intervals, difficulty, and schedule using SM‑2.
- ✅ **Card Feedback:** Mark answers as correct or incorrect and adapt future review timing.
- 🔄 **Next Card Logic:** Only one card shown at a time; next due card is surfaced intelligently.

### User & Course Management

- 👤 **User Login/Registration:** Secure authentication with hashed passwords.
- 📚 **Per-Course Organization:** All data is separated by course name and user.
- 🗂 **Local JSON Database:** All data is saved locally in `study_data.json`.

### AI Control

- 🔄 **Model Selector:** Choose between `gpt-4o`, `gpt-4.1`, or `gpt-3.5-turbo`.
- ✏️ **Custom Prompts:** Add your own instructions for summarizing, quizzes, and cards.

### Productivity Add-ons

- ✅ **To-Do List:** Add and remove personal todos to track tasks.
- 🗑️ **File Management:** Delete specific uploaded files per course.

---

## 🛠 Tech Stack

| Layer     | Tech                                                   |
| --------- | ------------------------------------------------------ |
| Backend   | Python, Flask, Flask-CORS, OpenAI API, PyMuPDF, Pillow |
| Frontend  | HTML, CSS, JavaScript (vanilla)                        |
| Storage   | Local JSON (`study_data.json`)                         |

---

## 🚀 Local Setup Guide (All-in-One)

Follow these steps to clone, set up, and run Wisebud locally.

### 1. Clone the Repository

```bash
git clone https://github.com/edwardnqin/2025-Summer-SAIL-Project.git
cd Summer-SAIL-Project

# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

echo OPENAI_API_KEY="sk-your-api-key" > .env

python backend/app.py
