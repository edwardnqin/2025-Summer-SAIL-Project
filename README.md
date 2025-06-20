# AcademiSpark

AcademiSpark is a smart study assistant that leverages the Google Gemini API to automatically generate flashcards and multiple-choice questions from your course materials. It uses a spaced repetition system (SRS) to schedule reviews, helping you learn more efficiently and retain information longer.

## Core Features

*   **AI-Powered Content Generation**: Automatically create flashcards and multiple-choice questions by pasting text or uploading PDF documents.
*   **Spaced Repetition System (SRS)**: The application tracks your performance on each card and schedules the next review at the optimal time to enhance long-term memory.
*   **Multiple Card Types**: Generates a mix of classic flashcards (question/answer) and multiple-choice questions to vary your study sessions.
*   **Performance-Based Learning**: Cards you find difficult will appear more frequently, while concepts you've mastered are shown less often.
*   **Integrated Break Timer**: Reminds you to take a 5-minute break after 25 minutes of studying to help maintain focus.

## Tech Stack

*   **Backend**: Python, Flask, `google-generativeai` for the Gemini API, `PyMuPDF` for PDF processing.
*   **Frontend**: HTML, CSS, and vanilla JavaScript.

## Setup and Installation

To run this project locally, follow these steps:

### 1. Clone the Repository

```bash
git clone https://github.com/ethanchang235/spaced-rep-study-assistant.git
cd spaced-rep-study-assistant```

### 2. Set Up the Backend

The backend server handles the logic for card generation and the spaced repetition algorithm.

```bash
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the required Python packages
pip install -r requirements.txt

*Note: If a `requirements.txt` file does not exist, you can create one or install the packages manually:*
`pip install flask google-generativeai python-dotenv Flask-Cors PyMuPDF`

### 3. Configure Environment Variables

You need to provide your Google Gemini API key.

1.  In the `backend` directory, create a new file named `.env`.
2.  Add your API key to this file as follows:

    ```
    GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    ```

## Running the Application

You will need two separate terminal windows to run the application.

### Terminal 1: Start the Backend Server

```bash
# In the backend directory with the virtual environment active
python app.py

```
The backend will now be running on `http://127.0.0.1:5001`.

### Terminal 2: Start the Frontend Server

```bash
# Navigate to the frontend directory
cd frontend

# Start Python's built-in HTTP server
python3 -m http.server 8000
```
The frontend will now be accessible in your browser.

### Access the Application

Open your web browser and navigate to:

`http://localhost:8000`

## How to Use

1.  **Provide Content**: Paste your study notes into the text area or click the "Choose a PDF or TXT File" button to upload a document.
2.  **Generate Cards**: Click the "Generate Study Cards" button. The AI will process your content and create a new set of flashcards.
3.  **Study**:
    *   For flashcards, think of the answer and click "Show Answer".
    *   For multiple-choice questions, select the option you believe is correct.
4.  **Rate Your Performance**: After revealing the answer, rate your confidence ("Hard", "Medium", or "Easy"). This will determine when you see the card next.
5.  **Keep Going**: Continue studying until the app tells you there are no more cards due for review.
6.  **Take Breaks**: The app will automatically prompt you to take a break after 25 minutes.