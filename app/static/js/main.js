document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('job-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const loader = submitBtn.querySelector('.loader');
    const resultsSection = document.getElementById('results-section');

    // State management
    let allSuggestions = [];
    let acceptedSuggestionIds = new Set();
    let originalResume = '';
    let currentSuggestionIndex = 0;

    // Tab Switching Logic
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.dataset.target;
            const parentGroup = button.closest('.form-group');

            // Deactivate all in this group
            parentGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            parentGroup.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            // Activate selected
            button.classList.add('active');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // Download Cover Letter Logic (unchanged)
    document.querySelectorAll('.download-btn[data-type="cover-letter"]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const content = document.getElementById('cover-letter-content').textContent;
            const filename = "Cover_Letter";

            const formData = new FormData();
            formData.append('content', content);
            formData.append('filename', filename);

            try {
                const response = await fetch('/api/download', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const docxBlob = new Blob([blob], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
                    const url = window.URL.createObjectURL(docxBlob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${filename}.docx`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                }
            } catch (error) {
                console.error('Download failed:', error);
                alert('Failed to download document.');
            }
        });
    });

    // Download Adapted Resume Logic (new)
    document.getElementById('download-adapted-resume')?.addEventListener('click', async () => {
        if (acceptedSuggestionIds.size === 0) {
            alert('Please accept at least one suggestion before downloading.');
            return;
        }

        try {
            // First, apply the changes
            const applyResponse = await fetch('/api/apply-changes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    original_resume: originalResume,
                    accepted_suggestion_ids: Array.from(acceptedSuggestionIds),
                    all_suggestions: allSuggestions
                })
            });

            if (!applyResponse.ok) {
                throw new Error('Failed to apply changes');
            }

            const { modified_resume } = await applyResponse.json();

            // Then download the modified resume
            const formData = new FormData();
            formData.append('content', modified_resume);
            formData.append('filename', 'Adapted_Resume');

            const downloadResponse = await fetch('/api/download', {
                method: 'POST',
                body: formData
            });

            if (downloadResponse.ok) {
                const blob = await downloadResponse.blob();
                const docxBlob = new Blob([blob], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
                const url = window.URL.createObjectURL(docxBlob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'Adapted_Resume.docx';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        } catch (error) {
            console.error('Download failed:', error);
            alert('Failed to download adapted resume.');
        }
    });

    // Render suggestions - One at a time
    function renderSuggestions(suggestions) {
        const container = document.getElementById('suggestions-container');
        const navigation = document.getElementById('suggestion-navigation');

        if (!suggestions || suggestions.length === 0) {
            container.innerHTML = `
                <div class="empty-suggestions">
                    <p>No suggestions available.</p>
                    <p style="font-size: 0.9rem;">The AI found that your resume is already well-aligned with the job description.</p>
                </div>
            `;
            navigation.classList.add('hidden');
            return;
        }

        // Show navigation controls
        navigation.classList.remove('hidden');

        // Reset to first suggestion
        currentSuggestionIndex = 0;
        renderCurrentSuggestion();
        updateNavigationButtons();
    }

    // Render the current suggestion based on index
    function renderCurrentSuggestion() {
        const container = document.getElementById('suggestions-container');
        const suggestion = allSuggestions[currentSuggestionIndex];

        if (!suggestion) return;

        container.innerHTML = `
            <div class="suggestion-card" data-id="${suggestion.id}">
                <div class="suggestion-header">
                    <span class="section-badge">${suggestion.section}</span>
                    <span class="priority-badge priority-${suggestion.priority}">${suggestion.priority.toUpperCase()} Priority</span>
                </div>
                
                <div class="diff-view">
                    <div class="original-text">
                        <del>${escapeHtml(suggestion.original_text)}</del>
                    </div>
                    <div class="arrow">↓</div>
                    <div class="suggested-text">
                        <ins>${escapeHtml(suggestion.suggested_text)}</ins>
                    </div>
                </div>
                
                <div class="reason">
                    <strong>Why:</strong> ${escapeHtml(suggestion.reason)}
                </div>
                
                <div class="actions">
                    <button class="accept-btn" data-id="${suggestion.id}">✓ Accept</button>
                    <button class="reject-btn" data-id="${suggestion.id}">✗ Reject</button>
                </div>
            </div>
        `;

        // Update card state based on accepted/rejected status
        const card = container.querySelector('.suggestion-card');
        const acceptBtn = card.querySelector('.accept-btn');
        const rejectBtn = card.querySelector('.reject-btn');

        if (acceptedSuggestionIds.has(suggestion.id)) {
            card.classList.add('accepted');
            acceptBtn.classList.add('active');
        } else if (card.classList.contains('rejected')) {
            card.classList.add('rejected');
            rejectBtn.classList.add('active');
        }

        // Add event listeners
        acceptBtn.addEventListener('click', () => toggleSuggestion(parseInt(acceptBtn.dataset.id), 'accept'));
        rejectBtn.addEventListener('click', () => toggleSuggestion(parseInt(rejectBtn.dataset.id), 'reject'));

        // Update counter
        updateCounter();
    }

    // Update navigation counter
    function updateCounter() {
        const counter = document.getElementById('nav-counter');
        counter.textContent = `Change ${currentSuggestionIndex + 1} of ${allSuggestions.length}`;
    }

    // Update navigation button states
    function updateNavigationButtons() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');

        prevBtn.disabled = currentSuggestionIndex === 0;
        nextBtn.disabled = currentSuggestionIndex === allSuggestions.length - 1;
    }

    // Navigation event listeners
    document.getElementById('prev-btn')?.addEventListener('click', () => {
        if (currentSuggestionIndex > 0) {
            currentSuggestionIndex--;
            renderCurrentSuggestion();
            updateNavigationButtons();
        }
    });

    document.getElementById('next-btn')?.addEventListener('click', () => {
        if (currentSuggestionIndex < allSuggestions.length - 1) {
            currentSuggestionIndex++;
            renderCurrentSuggestion();
            updateNavigationButtons();
        }
    });

    // Toggle suggestion acceptance
    function toggleSuggestion(id, action) {
        const card = document.querySelector(`.suggestion-card[data-id="${id}"]`);
        const acceptBtn = card.querySelector('.accept-btn');
        const rejectBtn = card.querySelector('.reject-btn');

        if (action === 'accept') {
            acceptedSuggestionIds.add(id);
            card.classList.add('accepted');
            card.classList.remove('rejected');
            acceptBtn.classList.add('active');
            rejectBtn.classList.remove('active');
        } else {
            acceptedSuggestionIds.delete(id);
            card.classList.add('rejected');
            card.classList.remove('accepted');
            acceptBtn.classList.remove('active');
            rejectBtn.classList.add('active');
        }

        updatePreview();
    }

    // Update preview with accepted changes
    async function updatePreview() {
        const previewBox = document.getElementById('resume-preview');

        if (acceptedSuggestionIds.size === 0) {
            previewBox.innerHTML = '<p style="color: var(--text-secondary);">Accept suggestions to preview changes...</p>';
            return;
        }

        try {
            const response = await fetch('/api/apply-changes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    original_resume: originalResume,
                    accepted_suggestion_ids: Array.from(acceptedSuggestionIds),
                    all_suggestions: allSuggestions
                })
            });

            if (response.ok) {
                const { modified_resume } = await response.json();
                previewBox.innerHTML = `<div class="markdown-body">${marked.parse(modified_resume)}</div>`;
            }
        } catch (error) {
            console.error('Preview update failed:', error);
        }
    }

    // Bulk actions
    document.querySelector('.accept-all-btn')?.addEventListener('click', () => {
        allSuggestions.forEach(s => {
            acceptedSuggestionIds.add(s.id);
            const card = document.querySelector(`.suggestion-card[data-id="${s.id}"]`);
            if (card) {
                card.classList.add('accepted');
                card.classList.remove('rejected');
                card.querySelector('.accept-btn').classList.add('active');
                card.querySelector('.reject-btn').classList.remove('active');
            }
        });
        updatePreview();
    });

    document.querySelector('.reject-all-btn')?.addEventListener('click', () => {
        acceptedSuggestionIds.clear();
        allSuggestions.forEach(s => {
            const card = document.querySelector(`.suggestion-card[data-id="${s.id}"]`);
            if (card) {
                card.classList.add('rejected');
                card.classList.remove('accepted');
                card.querySelector('.accept-btn').classList.remove('active');
                card.querySelector('.reject-btn').classList.add('active');
            }
        });
        updatePreview();
    });

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Reset state
        acceptedSuggestionIds.clear();
        allSuggestions = [];
        originalResume = '';

        // Show loading state
        submitBtn.disabled = true;
        btnText.textContent = 'Generating...';
        loader.classList.remove('hidden');
        resultsSection.classList.add('hidden');

        const formData = new FormData(form);

        // Remove file inputs if text tabs are active
        const resumeTextTab = document.querySelector('[data-target="resume-text-input"]');
        const jobTextTab = document.querySelector('[data-target="job-text-input"]');

        if (resumeTextTab && resumeTextTab.classList.contains('active')) {
            formData.delete('resume_file');
        }

        if (jobTextTab && jobTextTab.classList.contains('active')) {
            formData.delete('job_url');
        }

        try {
            const response = await fetch('/api/process-job', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Network response was not ok');
            }

            const data = await response.json();

            // Store data
            allSuggestions = data.resume_suggestions || [];
            originalResume = data.original_resume || '';

            // Populate results with Markdown rendering (with null checks)
            document.getElementById('job-summary-content').innerHTML = data.job_summary ? marked.parse(data.job_summary) : '<p>No job summary available</p>';
            document.getElementById('company-summary-content').innerHTML = data.company_summary ? marked.parse(data.company_summary) : '<p>No company summary available</p>';
            document.getElementById('cover-letter-content').innerHTML = data.cover_letter ? marked.parse(data.cover_letter) : '<p>No cover letter available</p>';

            // Render suggestions
            renderSuggestions(allSuggestions);

            // Initialize preview with the formatted original resume
            if (originalResume) {
                document.getElementById('resume-preview').innerHTML = `<div class="markdown-body">${marked.parse(originalResume)}</div>`;
            } else {
                document.getElementById('resume-preview').innerHTML = '<p style="color: var(--text-secondary);">Accept suggestions to preview changes...</p>';
            }

            // Show results
            resultsSection.classList.remove('hidden');

            // Scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });

        } catch (error) {
            console.error('Error:', error);
            console.error('Full error details:', error.message);
            alert(`Error: ${error.message || 'An error occurred. Please check your inputs and try again.'}`);
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            btnText.textContent = 'Generate Application Pack';
            loader.classList.add('hidden');
        }
    });

    // Helper function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
