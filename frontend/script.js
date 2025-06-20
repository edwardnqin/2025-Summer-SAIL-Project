document.addEventListener('DOMContentLoaded', () => {
    // CONFIG
    const API_URL = 'http://127.0.0.1:5001';
    const STUDY_SESSION_DURATION = 25 * 60 * 1000; // 25 minutes in milliseconds

    // DOM ELEMENTS
    const setupArea = document.getElementById('setup-area');
    const studyArea = document.getElementById('study-area');
    const generateBtn = document.getElementById('generate-btn');
    const topicInput = document.getElementById('topic-input');
    const statusMessage = document.getElementById('status-message');
    
    const cardContainer = document.getElementById('card-container');
    const questionText = document.getElementById('question-text');
    const answerText = document.getElementById('answer-text');
    const mcqOptionsContainer = document.getElementById('mcq-options');
    
    const showAnswerBtn = document.getElementById('show-answer-btn');
    const performanceBtns = document.getElementById('performance-btns');
    
    const cardFront = document.querySelector('.card-front');
    const cardBack = document.querySelector('.card-back');

    const breakReminder = document.getElementById('break-reminder');
    const resumeBtn = document.getElementById('resume-btn');

    // STATE
    let currentCard = null;
    let breakTimer = null;

    // FUNCTIONS

    const setStatus = (message, isLoading = false) => {
        statusMessage.textContent = message;
    };

    const startBreakTimer = () => {
        clearTimeout(breakTimer);
        breakTimer = setTimeout(() => {
            studyArea.classList.add('hidden');
            breakReminder.classList.remove('hidden');
        }, STUDY_SESSION_DURATION);
    };

    const fetchDueCard = async () => {
        setStatus('Loading next card...', true);
        try {
            const response = await fetch(`${API_URL}/get-due-card`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();

            if (data.message) {
                currentCard = null;
                setStatus(data.message);
                studyArea.classList.add('hidden');
                setupArea.classList.remove('hidden');
            } else {
                currentCard = data;
                displayCard(currentCard);
                setupArea.classList.add('hidden');
                studyArea.classList.remove('hidden');
                setStatus('');
                startBreakTimer();
            }
        } catch (error) {
            console.error('Error fetching due card:', error);
            setStatus('Error connecting to the backend. Is it running?');
        }
    };

    const displayCard = (card) => {
        cardFront.classList.remove('hidden');
        cardBack.classList.add('hidden');
        showAnswerBtn.classList.remove('hidden');
        performanceBtns.classList.add('hidden');
        mcqOptionsContainer.innerHTML = '';
        
        questionText.textContent = card.question;

        if (card.type === 'mcq') {
            showAnswerBtn.classList.add('hidden');
            
            card.options.forEach(option => {
                const button = document.createElement('button');
                button.className = 'mcq-option';
                button.textContent = option;
                button.onclick = () => handleMcqAnswer(button, option, card.correctAnswer);
                mcqOptionsContainer.appendChild(button);
            });
        } else {
            answerText.textContent = card.answer;
        }
    };
    
    const handleMcqAnswer = (buttonEl, selectedOption, correctOption) => {
        const allOptions = mcqOptionsContainer.querySelectorAll('.mcq-option');
        allOptions.forEach(btn => {
            btn.disabled = true;
            if (btn.textContent === correctOption) {
                btn.classList.add('correct');
            }
        });

        if (selectedOption !== correctOption) {
            buttonEl.classList.add('incorrect');
        }
        performanceBtns.classList.remove('hidden');
    };

    // EVENT LISTENERS

    generateBtn.addEventListener('click', async () => {
        const topic = topicInput.value.trim();
        if (!topic) {
            setStatus('Please enter a topic.');
            return;
        }

        setStatus('Generating new cards with Gemini... this may take a moment.', true);
        setupArea.classList.add('hidden');

        try {
            const response = await fetch(`${API_URL}/generate-cards`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: topic, count: 10 })
            });
            const data = await response.json();

            if (response.ok) {
                setStatus(data.message);
                fetchDueCard();
            } else {
                setStatus(`Error: ${data.error}`);
                setupArea.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Error generating cards:', error);
            setStatus('Failed to generate cards. Check the backend connection.');
            setupArea.classList.remove('hidden');
        }
    });

    showAnswerBtn.addEventListener('click', () => {
        cardBack.classList.remove('hidden');
        showAnswerBtn.classList.add('hidden');
        performanceBtns.classList.remove('hidden');
    });

    performanceBtns.addEventListener('click', async (e) => {
        if (e.target.matches('.perf-btn')) {
            const quality = e.target.dataset.quality;
            if (!currentCard) return;

            // Immediately fetch the next card for a snappy UI
            fetchDueCard(); 
            
            // Update the performance of the card we just answered in the background
            await fetch(`${API_URL}/update-card-performance`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cardId: currentCard.id, quality: quality })
            });
        }
    });
    
    resumeBtn.addEventListener('click', () => {
        breakReminder.classList.add('hidden');
        studyArea.classList.remove('hidden');
        startBreakTimer();
    });

    // INITIALIZATION
    fetchDueCard();
});
