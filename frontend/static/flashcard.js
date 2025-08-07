const API_URL = 'http://127.0.0.1:5001';

const qs = sel => document.querySelector(sel);
const fileListDiv = qs('#flashcard-file-list');
const questionText = qs('#question-text');
const answerText = qs('#answer-text');
const mcqOptions = qs('#mcq-options');
const showAnswerBtn = qs('#show-answer-btn');
const perfBtns = qs('#performance-btns');
const cardInner = qs('.card-inner');
const cardBack = qs('.card-back');
const cardFront = qs('.card-front');
const currentCourse = localStorage.getItem("currentCourse") || new URLSearchParams(window.location.search).get("course");

let currentCard = null;

// add a simple mapping from button text to SM‑2 quality scores
const ratingMap = { hard: 2, medium: 3, easy: 5 };

async function loadFiles() {
    const res = await fetch(`${API_URL}/list-files?course=${encodeURIComponent(currentCourse)}`, {
      headers: { "Username": localStorage.getItem("wisebudUser") }
    });
    const data = await res.json();

    document.querySelector('#flashcard-file-status')?.remove();

    if (!data.files.length) {
        fileListDiv.textContent = 'No files found.';
        return;
    }

    data.files.forEach(filename => {
        const wrapper = document.createElement('div');
        wrapper.className = 'file-item';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = filename;
        checkbox.name = 'selectedFiles';
        checkbox.id = `file-${filename}`;

        const label = document.createElement('label');
        label.textContent = filename;
        label.setAttribute('for', checkbox.id);


        wrapper.appendChild(checkbox);
        wrapper.appendChild(label);
        fileListDiv.appendChild(wrapper);
    });


    // === NEW: model selector and instruction box ===
    const modelLabel = document.createElement('label');
    modelLabel.textContent = 'Model:';
    const modelSelect = document.createElement('select');
    modelSelect.id = 'flashcard-model-select';
    ["gpt-5", "gpt-5-mini", "gpt-5-nano"].forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
    });
    modelLabel.appendChild(modelSelect);
    fileListDiv.appendChild(modelLabel);
    fileListDiv.appendChild(document.createElement('br'));

    const instrLabel = document.createElement('label');
    instrLabel.textContent = 'Instructions:';
    const instrTextarea = document.createElement('textarea');
    instrTextarea.id = 'flashcard-instructions';
    instrTextarea.rows = 3;
    instrTextarea.placeholder = 'Optional extra instructions...';
    instrLabel.appendChild(instrTextarea);
    fileListDiv.appendChild(instrLabel);
    fileListDiv.appendChild(document.createElement('br'));

    // Start Study button stays at the end
    const btn = document.createElement('button');
    btn.textContent = 'Start Study';
    btn.className = 'primary';
    btn.onclick = generateCards;
    fileListDiv.appendChild(btn);
}


async function generateCards() {
    const checked = document.querySelectorAll('#flashcard-file-list input:checked');
    const filenames = Array.from(checked).map(cb => cb.value);
    if (!filenames.length) return alert('Please select at least one file.');

    // === NEW: gather model and instructions ===
    const modelEl = document.getElementById('flashcard-model-select');
    const instrEl = document.getElementById('flashcard-instructions');
    const payload = { course: currentCourse, filenames };
    if (modelEl && modelEl.value) {
        payload.model = modelEl.value;
    }
    if (instrEl && instrEl.value.trim()) {
        payload.instructions = instrEl.value.trim();
    }
    const res = await fetch(`${API_URL}/generate-cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json',
                   'Username': localStorage.getItem("wisebudUser")
                 },
        body: JSON.stringify(payload)
    });

    const json = await res.json();
    if (!res.ok) return alert(json.error || 'Generation failed.');

    document.getElementById('flashcard-section')?.classList.remove('hidden');
    document.getElementById('file-select-section')?.classList.add('hidden');

    fetchNextCard();
}


async function fetchNextCard() {
    // NEW: pass the course as a query parameter
    const res = await fetch(`${API_URL}/get-card?course=${encodeURIComponent(currentCourse)}`, {
        headers: { 'Username': localStorage.getItem("wisebudUser") }
    });
    if (!res.ok) {
        questionText.textContent = 'No cards available.';
        return;
    }

    const card = await res.json();
    currentCard = card;
    displayCard(card);
}

function displayCard(card) {
    cardInner.classList.remove('flipped');
    cardFront.classList.remove('hidden');
    cardBack.classList.add('hidden');
    showAnswerBtn.classList.toggle('hidden', card.type === 'mcq');
    perfBtns.classList.add('hidden');
    mcqOptions.innerHTML = '';

    questionText.textContent = card.question;
    answerText.textContent = card.answer;
}

showAnswerBtn.addEventListener('click', () => {
    cardInner.classList.add('flipped');
    cardBack.classList.remove('hidden');
    showAnswerBtn.classList.add('hidden');
    perfBtns.classList.remove('hidden');
});

perfBtns.addEventListener('click', async e => {
    if (!e.target.matches('#performance-btns button')) return;

    const quality = parseInt(e.target.dataset.rating);
    if (!currentCard || !currentCard.id || isNaN(quality)) return;

    await fetch(`${API_URL}/answer-card`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Username": localStorage.getItem("wisebudUser")
        },
        body: JSON.stringify({ course: currentCourse, cardId: currentCard.id, quality })
    });

    fetchNextCard();
});

loadFiles();
