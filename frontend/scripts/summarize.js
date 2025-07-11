document.getElementById('summarize-button').addEventListener('click', () => {
    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');
    const summaryOutput = document.getElementById('summary-output');
    const summaryText = document.getElementById('summary-text');

    let textToSummarize = '';

    // Check if a file is uploaded
    if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        const reader = new FileReader();
        reader.onload = function (e) {
            textToSummarize = e.target.result;
            generateSummary(textToSummarize);
        };
        reader.readAsText(file);
    } else if (textInput.value.trim() !== '') {
        // Use pasted text
        textToSummarize = textInput.value.trim();
        generateSummary(textToSummarize);
    } else {
        alert('Please upload a file or paste text to summarize.');
    }

    function generateSummary(text) {
        // Simulate summary generation (replace with actual logic or API call)
        const summary = text.split(' ').slice(0, 20).join(' ') + '...';
        summaryText.textContent = summary;
        summaryOutput.classList.remove('hidden');
    }
});