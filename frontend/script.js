document.addEventListener('DOMContentLoaded', () => {
    /* CONFIG */
    const API_URL = 'http://127.0.0.1:5001';
    const STUDY_SESSION_DURATION = 25 * 60 * 1000; // 25-min focus block
  
    /* DOM SELECTORS */
    const setupArea = qs('#setup-area');
    const studyArea = qs('#study-area');
    const generateBtn = qs('#generate-btn');
    const summarizeBtn = qs('#summarize-btn');
    const chatForm = qs('#chat-form');
    const chatLog = qs('#chat-log');
    const statusMsg = qs('#status-message');
  
    const textInput = qs('#text-input');
    const fileUpload = qs('#file-upload');
    const fileNameDisplay = qs('#file-name-display');
  
    const cardContainer = qs('#card-container');
    const questionText = qs('#question-text');
    const answerText = qs('#answer-text');
    const mcqOptions = qs('#mcq-options');
  
    const showAnswerBtn = qs('#show-answer-btn');
    const perfBtns = qs('#performance-btns');
    const cardFront = qs('.card-front');
    const cardBack = qs('.card-back');
  
    const breakReminder = qs('#break-reminder');
    const resumeBtn = qs('#resume-btn');
  
    /* --------------- STATE ------------------ */
    let currentCard = null;
    let breakTimer;
  
    /* --------------- HELPERS ---------------- */
    function qs(sel) { return document.querySelector(sel); }
    const setStatus = (msg='') => statusMsg.textContent = msg;
    const startBreakTimer = () => {
      clearTimeout(breakTimer);
      breakTimer = setTimeout(() => {
        studyArea.classList.add('hidden');
        breakReminder.classList.remove('hidden');
      }, STUDY_SESSION_DURATION);
    };
  
    /* --------------- NEW BACKEND CALLS ------ */
    async function uploadFileOrText() {
      const txt = textInput.value.trim();
      const file = fileUpload.files[0];
      if (!txt && !file) { setStatus('Paste text or choose a file.'); return false; }
  
      const fd = new FormData();
      txt ? fd.append('text_content', txt) : fd.append('file', file);
  
      const r = await fetch(`${API_URL}/upload`, { method:'POST', body: fd });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || 'upload failed');
      return true;
    }
  
    async function fetchSummary() {
      const r = await fetch(`${API_URL}/summarize`);
      const {summary, error} = await r.json();
      if (error) throw new Error(error);
      qs('#summary-box').textContent = summary;
    }
  
    async function askModel(q) {
      const r = await fetch(`${API_URL}/ask`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({query:q})
      });
      const {answer,error} = await r.json();
      if (error) throw new Error(error);
      return answer;
    }
  
    /* --------------- FLASH-CARD LOGIC ------- */
    const fetchDueCard = async () => {
      setStatus('Loading next card...');
      const r = await fetch(`${API_URL}/get-due-card`);
      if (!r.ok) { setStatus('Backend error'); return; }
      const data = await r.json();
      if (data.message) {
        currentCard=null; setStatus(data.message);
        studyArea.classList.add('hidden'); setupArea.classList.remove('hidden');
      } else {
        currentCard=data; displayCard(data);
        setupArea.classList.add('hidden'); studyArea.classList.remove('hidden');
        setStatus(''); startBreakTimer();
      }
    };
  
    function displayCard(card){
      cardFront.classList.remove('hidden'); cardBack.classList.add('hidden');
      showAnswerBtn.classList.remove('hidden'); perfBtns.classList.add('hidden');
      mcqOptions.innerHTML='';
      questionText.textContent=card.question;
      if(card.type==='mcq'){
        showAnswerBtn.classList.add('hidden');
        card.options.forEach(opt=>{
          const btn=document.createElement('button');
          btn.className='mcq-option'; btn.textContent=opt;
          btn.onclick=()=>handleMcq(btn,opt,card.correctAnswer);
          mcqOptions.appendChild(btn);
        });
      }else{ answerText.textContent=card.answer; }
    }
  
    const handleMcq=(btn,opt,correct)=>{
      mcqOptions.querySelectorAll('.mcq-option').forEach(b=>{
        b.disabled=true; if(b.textContent===correct)b.classList.add('correct');
      });
      if(opt!==correct)btn.classList.add('incorrect');
      perfBtns.classList.remove('hidden');
    };
  
    /* --------------- EVENT BINDINGS --------- */
    fileUpload.onchange=()=>{
      if(fileUpload.files.length){
        fileNameDisplay.textContent=fileUpload.files[0].name;
        textInput.value=''; textInput.disabled=true; textInput.style.background='#f8f9fa';
      }
    };
  
    generateBtn.onclick=async()=>{
      try{
        setStatus('Uploading and generating cards...');
        await uploadFileOrText();
        const r=await fetch(`${API_URL}/generate-cards`,{method:'POST'});
        const j=await r.json();
        if(!r.ok)throw new Error(j.error); setStatus(j.message);
        fetchDueCard();
      }catch(e){ setStatus(e.message); setupArea.classList.remove('hidden'); }
    };
  
    summarizeBtn.onclick=async()=>{
      try{ setStatus('Summarizing...'); await fetchSummary(); setStatus(''); }
      catch(e){ setStatus(e.message); }
    };
  
    chatForm.onsubmit=async(e)=>{
      e.preventDefault();
      const q=qs('#chat-input').value.trim(); if(!q)return;
      chatLog.value+=`You: ${q}\n`; qs('#chat-input').value='';
      chatLog.scrollTop=chatLog.scrollHeight;
      try{
        const a=await askModel(q);
        chatLog.value+=`AI: ${a}\n\n`; chatLog.scrollTop=chatLog.scrollHeight;
      }catch(err){ chatLog.value+=`[error: ${err.message}]\n`; }
    };
  
    showAnswerBtn.onclick=()=>{
      cardBack.classList.remove('hidden'); showAnswerBtn.classList.add('hidden');
      perfBtns.classList.remove('hidden');
    };
  
    perfBtns.onclick=async(e)=>{
      if(!e.target.matches('.perf-btn'))return;
      await fetch(`${API_URL}/update-card-performance`,{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({cardId:currentCard.id,quality:e.target.dataset.quality})
      });
      fetchDueCard();
    };
  
    resumeBtn.onclick=()=>{ breakReminder.classList.add('hidden'); studyArea.classList.remove('hidden'); startBreakTimer(); };
  
    /* --------------- INIT ------------------- */
    fetchDueCard();
  });
  