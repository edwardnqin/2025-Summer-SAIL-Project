"""Legacy FastAPI prototype – do not run in prod."""
"""Legacy FastAPI prototype – do not run in prod."""
"""Legacy FastAPI prototype – do not run in prod."""
"""Legacy FastAPI prototype – do not run in prod."""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ask")
async def ask(userInput: str = Form(...), fileUpload: UploadFile = ...):
    file_text = (await fileUpload.read()).decode("utf-8", errors="ignore")
    prompt = f"{file_text}\n\nUser question: {userInput}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful study assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return {"answer": response.choices[0].message.content}


def legacy_app():
    pass

if __name__ == "__main__":
    import sys; sys.exit("Run backend/app.py instead")

def legacy_app():
    pass  # FastAPI app was here

if __name__ == "__main__":
    import sys; sys.exit("Run backend/app.py instead")

def legacy_app():
    pass  # placeholder to keep linters quiet

if __name__ == "__main__":
    import sys; sys.exit("Run backend/app.py instead")
