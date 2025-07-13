const API_URL = 'http://127.0.0.1:5001';

let questions = [];
let currentIndex = 0;
let answers = Array(10).fill(null);
let score = 0;
let timerInterval = null;
let timeLeft = 10 * 60; // 10 minutes default

const qs = sel => document.querySelector(sel);

const fileListDiv = qs('#quiz-file-list');
const quizSection = qs('#quiz-section');
const questionDiv = qs('#quiz-question');
const optionsDiv = qs('#quiz-options');
const progressDiv = qs('#quiz-progress');
const timerDisplay = qs('#quiz-timer');

function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function startTimer() {
  timerDisplay.textContent = formatTime(timeLeft);
  timerInterval = setInterval(() => {
    timeLeft--;
    timerDisplay.textContent = formatTime(timeLeft);
    if (timeLeft <= 0) {
      clearInterval(timerInterval);
      alert("Time's up! Auto-submitting your quiz.");
      showResults();
    }
  }, 1000);
}

async function loadFiles() {
  const res = await fetch(`${API_URL}/list-files`);
  const data = await res.json();

  if (!data.files.length) {
    fileListDiv.textContent = 'No files found.';
    return;
  }

  data.files.forEach(filename => {
    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = filename;
    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(filename));
    fileListDiv.appendChild(label);
    fileListDiv.appendChild(document.createElement('br'));
  });

  const btn = document.createElement('button');
  btn.textContent = 'Start Quiz';
  btn.className = 'primary';
  btn.onclick = generateQuiz;
  fileListDiv.appendChild(btn);
}

async function generateQuiz() {
  const checked = document.querySelectorAll('#quiz-file-list input:checked');
  const filenames = Array.from(checked).map(cb => cb.value);
  if (!filenames.length) return alert('Please select at least one file.');

  const res = await fetch(`${API_URL}/generate-quiz`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filenames })
  });
  const data = await res.json();

  questions = data.questions.slice(0, 10);
  currentIndex = 0;
  answers = Array(10).fill(null);
  score = 0;
  timeLeft = 10 * 60;
  quizSection.classList.remove('hidden');
  startTimer();
  renderQuestion();
}

function renderQuestion() {
  const q = questions[currentIndex];
  questionDiv.innerHTML = `<strong>Q${currentIndex + 1}:</strong> ${q.question}`;
  optionsDiv.innerHTML = '';

  Object.entries(q.options).forEach(([key, val]) => {
    const btn = document.createElement('button');
    btn.textContent = `${key}. ${val}`;
    btn.className = 'secondary';
    if (answers[currentIndex] === key) btn.classList.add('selected');
    btn.onclick = () => {
      answers[currentIndex] = key;
      renderQuestion();
    };
    optionsDiv.appendChild(btn);
  });

  renderProgress();
}

function renderProgress() {
  progressDiv.innerHTML = '';
  questions.forEach((_, i) => {
    const span = document.createElement('span');
    span.textContent = i + 1;
    span.className = 'progress-dot';
    if (answers[i]) span.classList.add('answered');
    if (i === currentIndex) span.classList.add('current');
    span.onclick = () => {
      currentIndex = i;
      renderQuestion();
    };
    progressDiv.appendChild(span);
  });

  if (answers.every(ans => ans !== null)) {
    const submitBtn = document.createElement('button');
    submitBtn.textContent = 'Submit Quiz';
    submitBtn.className = 'primary';
    submitBtn.onclick = showResults;
    progressDiv.appendChild(submitBtn);
  }
}

function showResults() {
  clearInterval(timerInterval);
  score = 0;
  const results = questions.map((q, i) => {
    const correct = q.correctAnswer;
    const selected = answers[i];
    const isCorrect = correct === selected;
    if (isCorrect) score++;
    return `Q${i + 1}: ${isCorrect ? '✅' : '❌'} Selected: ${selected || 'None'} | Correct: ${correct}`;
  }).join('<br>');

  let scoreClass = 'score-good';
  if (score <= 4) scoreClass = 'score-bad';
  else if (score <= 7) scoreClass = 'score-average';

  questionDiv.innerHTML = `<h2>Your Score: <span class="${scoreClass}">${score}/10</span></h2><br>${results}`;
  optionsDiv.innerHTML = '';
  progressDiv.innerHTML = '';
  timerDisplay.textContent = '';
}

qs('#prev-btn').onclick = () => {
  if (currentIndex > 0) currentIndex--;
  renderQuestion();
};

qs('#next-btn').onclick = () => {
  if (currentIndex < questions.length - 1) currentIndex++;
  renderQuestion();
};

loadFiles();