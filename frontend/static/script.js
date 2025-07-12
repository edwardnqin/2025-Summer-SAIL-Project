document.addEventListener('DOMContentLoaded', () => {
  /* CONFIG */
  const API_URL = 'http://127.0.0.1:5001';

  // Durations for Pomodoro-style sessions
  const WORK_SESSION_DURATION  = 20 * 60 * 1000;
  const BREAK_SESSION_DURATION = 10 * 60 * 1000;

  /* DOM SELECTORS */
  const qs = sel => document.querySelector(sel);

  const setupArea       = qs('#setup-area');
  const studyArea       = qs('#study-area');
  const generateBtn     = qs('#generate-btn');
  const summarizeBtn    = qs('#summarize-btn');
  const chatForm        = qs('#chat-form');
  const chatLog         = qs('#chat-log');
  const chatSection     = qs('#chat-section');
  const statusMsg       = qs('#status-message');

  const sourceSelect    = qs('#source-select');
  const panelLocal      = qs('#panel-local');
  const panelDrive      = qs('#panel-drive');
  const panelBackend    = qs('#panel-backend');
  const drivePickerBtn  = qs('#drive-picker-btn');
  const driveFileName   = qs('#drive-file-name');
  const loadJsonBtn     = qs('#load-json-btn');
  const backendStatus   = qs('#backend-status');

  const textInput       = qs('#text-input');
  const fileUpload      = qs('#file-upload');
  const fileNameDisplay = qs('#file-name-display');

  const questionText    = qs('#question-text');
  const answerText      = qs('#answer-text');
  const mcqOptions      = qs('#mcq-options');

  const showAnswerBtn   = qs('#show-answer-btn');
  const perfBtns        = qs('#performance-btns');
  const cardFront       = qs('.card-front');
  const cardBack        = qs('.card-back');

  const breakReminder   = qs('#break-reminder');
  const resumeBtn       = qs('#resume-btn');

  const timerDisplay    = qs('#timer-display text');
  const timerInput      = qs('#timer-input');
  const setTimerBtn     = qs('#set-timer-btn');
  const startTimerBtn   = qs('#start-timer-btn');
  const timerModal      = qs('#timer-modal');
  const saveTimerBtn    = qs('#save-timer-btn');
  const cancelTimerBtn  = qs('#cancel-timer-btn');

  /* STATE */
  let currentCard = null;
  let workTimer, breakTimer;
  let timeLeft = 25 * 60;
  let timerInterval = null;

  /* HELPERS */
  const setStatus = msg => statusMsg.textContent = msg;

  function startWorkTimer() {
    clearTimeout(workTimer);
    clearTimeout(breakTimer);

    workTimer = setTimeout(() => {
      // hide study, show break overlay
      studyArea.classList.add('hidden');
      breakReminder.classList.remove('hidden');

      // auto-resume after break
      breakTimer = setTimeout(() => {
        breakReminder.classList.add('hidden');
        studyArea.classList.remove('hidden');
        startWorkTimer();
      }, BREAK_SESSION_DURATION);

    }, WORK_SESSION_DURATION);
  }

  function updateClock() {
    const m = Math.floor(timeLeft / 60);
    const s = timeLeft % 60;
    timerDisplay.textContent = `${m}:${s.toString().padStart(2, '0')}`;
  }

  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  /* BACKEND CALLS */
  async function uploadFileOrText() {
    const fd = new FormData();
    if (sourceSelect.value === 'local') {
      const txt  = textInput.value.trim();
      const file = fileUpload.files[0];
      if (!txt && !file) { setStatus('Paste text or choose a file.'); return false; }
      if (txt)  fd.append('text_content', txt);
      else      fd.append('file', file);
    } else if (sourceSelect.value === 'drive') {
      if (!window.chosenDriveFile) { setStatus('No Drive file selected.'); return false; }
      fd.append('file', window.chosenDriveFile);
    } else {
      const txt = textInput.value.trim();
      if (!txt) { setStatus('No data loaded from backend.'); return false; }
      fd.append('text_content', txt);
    }

    const res = await fetch(`${API_URL}/upload`, { method:'POST', body: fd });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Upload failed');
    return true;
  }

  async function fetchSummary() {
    const res = await fetch(`${API_URL}/summarize`);
    const { summary, error } = await res.json();
    if (error) throw new Error(error);
    qs('#summary-box').textContent = summary;
  }

  async function askModel(q) {
    const res = await fetch(`${API_URL}/ask`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ query: q })
    });
    const { answer, error } = await res.json();
    if (error) throw new Error(error);
    return answer;
  }

  /* FLASHCARD LOGIC */
  async function fetchDueCard() {
    setStatus('Loading next card…');
    const res = await fetch(`${API_URL}/get-due-card`);
    if (!res.ok) { setStatus('Backend error'); return; }
    const data = await res.json();

    if (data.message) {
      currentCard = null;
      setStatus(data.message);
      studyArea.classList.add('hidden');
      setupArea.classList.remove('hidden');
    } else {
      currentCard = data;
      displayCard(data);
      setupArea.classList.add('hidden');
      studyArea.classList.remove('hidden');
      setStatus('');
      startWorkTimer();
    }
  }

  function displayCard(card) {
    cardFront.classList.remove('hidden');
    cardBack.classList.add('hidden');
    showAnswerBtn.classList.toggle('hidden', card.type === 'mcq');
    perfBtns.classList.add('hidden');
    mcqOptions.innerHTML = '';

    questionText.textContent = card.question;
    if (card.type === 'mcq') {
      card.options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'secondary mcq-option';
        btn.textContent = opt;
        btn.onclick = () => handleMcq(btn, opt, card.correctAnswer);
        mcqOptions.appendChild(btn);
      });
    } else {
      answerText.textContent = card.answer;
    }
  }

  function handleMcq(btn, opt, correct) {
    mcqOptions.querySelectorAll('.mcq-option').forEach(b => {
      b.disabled = true;
      if (b.textContent === correct) b.classList.replace('secondary','primary');
    });
    if (opt !== correct) btn.classList.add('incorrect');
    perfBtns.classList.remove('hidden');
  }

  /* EVENT BINDINGS */
  fileUpload.addEventListener('change', () => {
    if (fileUpload.files.length) {
      fileNameDisplay.textContent = fileUpload.files[0].name;
      textInput.value = '';
      textInput.disabled = true;
    }
  });

  generateBtn.addEventListener('click', async () => {
    try {
      setStatus('Uploading & generating cards…');
      await uploadFileOrText();
      const res = await fetch(`${API_URL}/generate-cards`, { method:'POST' });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error);
      setStatus(json.message);
      await fetchDueCard();
    } catch (err) {
      setStatus(err.message);
      setupArea.classList.remove('hidden');
    }
  });

  summarizeBtn.addEventListener('click', async () => {
    try {
      setStatus('Summarizing…');
      await fetchSummary();
      setStatus('');
    } catch (err) {
      setStatus(err.message);
    }
  });

  sourceSelect.addEventListener('change', () => {
    panelLocal.classList.toggle('hidden', sourceSelect.value !== 'local');
    panelDrive.classList.toggle('hidden', sourceSelect.value !== 'drive');
    panelBackend.classList.toggle('hidden', sourceSelect.value !== 'backend');
  });

  drivePickerBtn.addEventListener('click', async () => {
    try {
      // TODO: integrate Google Picker
      const file = await pickFileFromDrive();
      driveFileName.textContent = file.name;
      window.chosenDriveFile = file;
    } catch {
      driveFileName.textContent = 'Drive picker error';
    }
  });

  loadJsonBtn.addEventListener('click', async () => {
    backendStatus.textContent = 'Loading…';
    try {
      const res = await fetch(`${API_URL}/notes/json`);
      if (!res.ok) throw new Error('Fetch failed');
      const data = await res.json();
      textInput.value = data.content;
      backendStatus.textContent = 'Loaded!';
      sourceSelect.value = 'local';
      sourceSelect.dispatchEvent(new Event('change'));
    } catch {
      backendStatus.textContent = 'Error loading JSON';
    }
  });

  chatForm.addEventListener('submit', async e => {
    e.preventDefault();
    const q = qs('#chat-input').value.trim();
    if (!q) return;
    chatLog.value += `You: ${q}\n`;
    qs('#chat-input').value = '';
    chatLog.scrollTop = chatLog.scrollHeight;
    try {
      const a = await askModel(q);
      chatLog.value += `AI: ${a}\n\n`;
      chatLog.scrollTop = chatLog.scrollHeight;
    } catch (err) {
      chatLog.value += `[error: ${err.message}]\n`;
    }
  });

  showAnswerBtn.addEventListener('click', () => {
    cardBack.classList.remove('hidden');
    showAnswerBtn.classList.add('hidden');
    perfBtns.classList.remove('hidden');
  });

  perfBtns.addEventListener('click', async e => {
    if (!e.target.matches('.perf-btn')) return;
    await fetch(`${API_URL}/update-card-performance`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        cardId: currentCard.id,
        quality: e.target.dataset.quality
      })
    });
    fetchDueCard();
  });

  resumeBtn.addEventListener('click', () => {
    breakReminder.classList.add('hidden');
    studyArea.classList.remove('hidden');
    startWorkTimer();
  });

  /* TIMER MODAL LOGIC */
  setTimerBtn.addEventListener('click', () => {
    timerModal.classList.remove('hidden');
    timerInput.value = formatTime(timeLeft);
  });

  saveTimerBtn.addEventListener('click', () => {
    const [m, s] = timerInput.value.split(':').map(Number);
    if (!isNaN(m) && !isNaN(s)) {
      timeLeft = m * 60 + s;
      updateClock();
      timerModal.classList.add('hidden');
    } else {
      alert('Use mm:ss format');
    }
  });

  cancelTimerBtn.addEventListener('click', () => {
    timerModal.classList.add('hidden');
  });

  startTimerBtn.addEventListener('click', () => {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (timeLeft > 0) {
        timeLeft--;
        updateClock();
      } else {
        clearInterval(timerInterval);
        playAlarm();
      }
    }, 1000);
  });

  function playAlarm() {
    const audio = new Audio('alarm.mp3');
    audio.play();
  }

  /* INIT */
  fetchDueCard();
  updateClock();
});
