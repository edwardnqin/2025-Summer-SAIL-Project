document.addEventListener('DOMContentLoaded', () => {
  const API_URL = 'http://127.0.0.1:5001';
  const qs = sel => document.querySelector(sel);

  const timerCircle = qs('#clock-svg circle');
  const radius = timerCircle.r.baseVal.value;
  const circumference = 2 * Math.PI * radius;
  timerCircle.style.strokeDasharray = circumference;
  timerCircle.style.strokeDashoffset = circumference;

  const setupArea = qs('#setup-area');
  const studyArea = qs('#study-area');
  const generateBtn = qs('#generate-btn');
  const summarizeBtn = qs('#summarize-btn');
  const chatForm = qs('#chat-form');
  const chatInput = qs('#chat-input');
  const chatLog = qs('#chat-log');
  const statusMsg = qs('#status-message');

  const sourceSelect = qs('#source-select');
  const panelLocal = qs('#panel-local');
  const panelDrive = qs('#panel-drive');
  const panelBackend = qs('#panel-backend');
  const drivePickerBtn = qs('#drive-picker-btn');
  const driveFileName = qs('#drive-file-name');
  const loadJsonBtn = qs('#load-json-btn');
  const backendStatus = qs('#backend-status');
  const textInput = qs('#text-input');

  const fileUpload = qs('#file-upload');
  const fileList = qs('#file-list');
  const fileNameDisplay = qs('#file-name-display');

  const questionText = qs('#question-text');
  const answerText = qs('#answer-text');
  const mcqOptions = qs('#mcq-options');

  const showAnswerBtn = qs('#show-answer-btn');
  const perfBtns = qs('#performance-btns');
  const cardFront = qs('.card-front');
  const cardBack = qs('.card-back');

  const cardContainer = qs('#card-container');
  const cardInner = qs('#card-container .card-inner');

  const breakReminder = qs('#break-reminder');
  const resumeBtn = qs('#resume-btn');

  const timerDisplay = qs('#clock-svg text');
  const timerInput = qs('#timer-input');
  const setTimerBtn = qs('#set-timer-btn');
  const startTimerBtn = qs('#start-timer-btn');
  const pauseTimerBtn = qs('#pause-timer-btn');
  const timerModal = qs('#timer-modal');
  const saveTimerBtn = qs('#save-timer-btn');
  const cancelTimerBtn = qs('#cancel-timer-btn');

  let currentCard = null;
  let cachedFiles = [];
  let timerInterval = null;
  let timeLeft = 25 * 60;
  let initialTime = timeLeft;

  const setStatus = msg => statusMsg.textContent = msg;

  function formatTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function updateClock() {
    timerDisplay.textContent = formatTime(timeLeft);
    const progress = timeLeft / initialTime;
    timerCircle.style.strokeDashoffset = circumference * (1 - progress);
  }

  async function uploadFileOrText() {
    const fd = new FormData();
    if (sourceSelect.value === 'local') {
      if (!cachedFiles.length) { setStatus('Please choose at least one file.'); return false; }
      for (const file of cachedFiles) {
        fd.append('files', file);
      }
    } else if (sourceSelect.value === 'drive') {
      if (!window.chosenDriveFile) { setStatus('No Drive file selected.'); return false; }
      fd.append('files', window.chosenDriveFile);
    } else {
      const txt = textInput.value.trim();
      if (!txt) { setStatus('No data loaded from backend.'); return false; }
      fd.append('text_content', txt);
    }

    const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: fd });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || 'Upload failed');
    return true;
  }

  async function displayUploadedFiles() {
    try {
      const res = await fetch(`${API_URL}/list-files`);
      const data = await res.json();
      fileList.innerHTML = '';
      data.files.forEach(name => {
        const li = document.createElement('li');
        li.textContent = name;

        const delBtn = document.createElement('button');
        delBtn.textContent = '❌';
        delBtn.className = 'secondary delete-btn';
        delBtn.onclick = async () => {
          const confirmDel = confirm(`Delete all '${name}'?`);
          if (!confirmDel) return;
          const res = await fetch(`${API_URL}/delete-file`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: name })
          });
          const msg = await res.json();
          setStatus(msg.message || 'Deleted.');
          await displayUploadedFiles();
        };

        li.appendChild(delBtn);
        fileList.appendChild(li);
      });
    } catch (err) {
      console.error('Error loading files:', err);
    }
  }

  async function askModel(q) {
    const res = await fetch(`${API_URL}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    });
    const { answer, error } = await res.json();
    if (error) throw new Error(error);
    return answer;
  }

  async function fetchDueCard() {
    setStatus('Loading next card…');
    const res = await fetch(`${API_URL}/get-due-card`);
    const data = await res.json();
    if (!res.ok || data.message) {
      currentCard = null;
      setStatus(data.message || 'No cards.');
      studyArea?.classList.add('hidden');
      setupArea?.classList.remove('hidden');
      return;
    }

    currentCard = data;
    displayCard(data);
    setupArea?.classList.add('hidden');
    studyArea?.classList.remove('hidden');
    setStatus('');
  }

  function displayCard(card) {
    cardInner.classList.remove('flipped');
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
      if (b.textContent === correct) b.classList.replace('secondary', 'primary');
    });
    if (opt !== correct) btn.classList.add('incorrect');
    perfBtns.classList.remove('hidden');
  }

  generateBtn.addEventListener('click', async () => {
    try {
      setStatus('Uploading files…');
      const success = await uploadFileOrText();
      if (success) {
        await displayUploadedFiles();
        setStatus('Files uploaded successfully.');
      }
    } catch (err) {
      setStatus(err.message);
    }
  });

  summarizeBtn.addEventListener('click', () => {
    window.location.href = 'summarize.html';
  });

  fileUpload.addEventListener('change', () => {
    if (fileUpload.files.length) {
      const selectedFiles = Array.from(fileUpload.files);
      const names = new Set(cachedFiles.map(f => f.name));
      selectedFiles.forEach(f => {
        if (!names.has(f.name)) cachedFiles.push(f);
      });

      const ul = document.createElement('ul');
      ul.style.margin = '0';
      ul.style.paddingLeft = '16px';
      cachedFiles.forEach(file => {
        const li = document.createElement('li');
        li.textContent = file.name;
        ul.appendChild(li);
      });
      fileNameDisplay.innerHTML = '';
      fileNameDisplay.appendChild(ul);
    }
  });

  sourceSelect.addEventListener('change', () => {
    panelLocal.classList.toggle('hidden', sourceSelect.value !== 'local');
    panelDrive.classList.toggle('hidden', sourceSelect.value !== 'drive');
    panelBackend.classList.toggle('hidden', sourceSelect.value !== 'backend');
  });

  drivePickerBtn.addEventListener('click', async () => {
    try {
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
    const q = chatInput.value.trim();
    if (!q) return;
    chatLog.value += `You: ${q}\n`;
    chatInput.value = '';
    chatLog.scrollTop = chatLog.scrollHeight;

    try {
      const a = await askModel(q);
      chatLog.value += `AI: ${a}\n\n`;
      chatLog.scrollTop = chatLog.scrollHeight;
    } catch (err) {
      chatLog.value += `[error: ${err.message}]\n`;
    }
  });

  showAnswerBtn?.addEventListener('click', () => {
    cardInner.classList.add('flipped');
    cardBack.classList.remove('hidden');
    showAnswerBtn.classList.add('hidden');
    perfBtns.classList.remove('hidden');
  });

  cardContainer?.addEventListener('click', () => {
    cardInner.classList.toggle('flipped');
  });

  perfBtns?.addEventListener('click', async e => {
    if (!e.target.matches('#performance-btns button')) return;
    const quality = e.target.dataset.rating;
    await fetch(`${API_URL}/update-card-performance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cardId: currentCard.id, quality })
    });
    fetchDueCard();
  });

  resumeBtn?.addEventListener('click', () => {
    breakReminder.classList.add('hidden');
    studyArea.classList.remove('hidden');
  });

  setTimerBtn?.addEventListener('click', () => {
    timerModal.classList.remove('hidden');
    timerInput.value = formatTime(timeLeft);
  });

  saveTimerBtn?.addEventListener('click', () => {
    const parts = timerInput.value.split(':').map(Number);
    if (parts.length === 3) {
      const [h, m, s] = parts;
      if (!isNaN(h) && h >= 0 && !isNaN(m) && m < 60 && !isNaN(s) && s < 60) {
        timeLeft = h * 3600 + m * 60 + s;
        initialTime = timeLeft;
        updateClock();
        timerModal.classList.add('hidden');
        return;
      }
    }
    alert('Please enter time as hh:mm:ss, with 0≤mm,ss<60.');
  });

  cancelTimerBtn?.addEventListener('click', () => {
    timerModal.classList.add('hidden');
  });

  startTimerBtn?.addEventListener('click', () => {
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

  pauseTimerBtn?.addEventListener('click', () => {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
      setStatus('Timer paused');
    }
  });

  function playAlarm() {
    const audio = new Audio('alarm.mp3');
    audio.play();
  }

  // INIT
  displayUploadedFiles();
  fetchDueCard();
  updateClock();
});
