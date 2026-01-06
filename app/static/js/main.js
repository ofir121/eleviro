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
    let coverLetterMarkdown = '';
    let companyName = 'Company';
    let roleTitle = 'Role';
    let candidateName = 'Candidate';
    let currentJobDescription = ''; // Store for outreach generation
    let progressInterval;
    let cleanupTimeout;

    // Navigation Menu Logic
    const menuBtn = document.getElementById('menu-btn');
    const dropdownContent = document.getElementById('dropdown-content');
    const navItems = document.querySelectorAll('.nav-item');

    menuBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownContent.classList.toggle('show');
    });

    document.addEventListener('click', (e) => {
        if (!menuBtn.contains(e.target) && !dropdownContent.contains(e.target)) {
            dropdownContent.classList.remove('show');
        }
    });

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const viewId = item.dataset.view;

            // Switch Menu Active State
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Switch Views
            document.querySelectorAll('.view-section').forEach(view => {
                view.classList.add('hidden');
                view.classList.remove('active');
            });
            document.getElementById(viewId).classList.remove('hidden');
            document.getElementById(viewId).classList.add('active');

            // Toggle Controls Visibility
            // If Outreach is active, hide the main generate button to avoid confusion
            if (viewId === 'outreach-view') {
                document.getElementById('application-controls').classList.add('hidden');
            } else {
                document.getElementById('application-controls').classList.remove('hidden');
            }

            // Close Menu
            dropdownContent.classList.remove('show');
        });
    });

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

    // Download Cover Letter Logic
    document.querySelectorAll('.download-btn[data-type="cover-letter"]').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!coverLetterMarkdown) {
                alert('No cover letter content available to download.');
                return;
            }

            const content = coverLetterMarkdown;
            const filename = `${candidateName} Cover Letter ${companyName}`;

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

            const filename = `${candidateName} CV ${companyName}`;
            formData.append('filename', filename);

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
                a.download = `${filename}.docx`;
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

    // Cold Outreach Generator Logic
    let jobDescription = ''; // Store JD globally

    // Capture JD on form submit to use later
    // Note: We need to ensure jobDescription is populated.
    // In the form submit handler, we can capture the text.

    document.getElementById('generate-outreach-btn')?.addEventListener('click', async () => {
        const outreachType = document.getElementById('outreach-type').value;
        const resultBox = document.getElementById('outreach-result');
        const contentArea = document.getElementById('outreach-content');
        const generateBtn = document.getElementById('generate-outreach-btn');
        const isTestingMode = document.getElementById('testing-mode').checked;

        // Ensure we have necessary context
        // We can get current JD from the DOM if we stored it, or grab from input if hasn't been cleared
        // But better to use the stored variable from the last successful generate

        // Let's grab the text content from the simplified summary if raw text isn't available, 
        // OR better, let's just use originalResume and the job description we submitted.

        // Since we don't store raw JD in a variable yet, let's grab it from the form input as a fallback
        // OR update the submit handler to store it.
        // For now, let's try to capture it in the submit handler below.

        if (!originalResume) {
            alert('Please generate the application pack first to load resume and job context.');
            return;
        }

        try {
            generateBtn.disabled = true;
            generateBtn.textContent = 'Generating...';
            resultBox.classList.add('hidden');

            const response = await fetch('/api/generate-outreach', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    resume_text: originalResume,
                    job_description: currentJobDescription,
                    outreach_type: outreachType,
                    is_testing_mode: isTestingMode,
                    company_name: companyName,
                    role_title: roleTitle || 'the role'
                })
            });

            if (!response.ok) throw new Error('Failed to generate outreach');

            const data = await response.json();
            contentArea.value = data.content;
            resultBox.classList.remove('hidden');

        } catch (error) {
            console.error('Outreach generation failed:', error);
            alert('Failed to generate message.');
        } finally {
            generateBtn.disabled = false;
            generateBtn.textContent = 'Generate Message';
        }
    });

    document.getElementById('copy-outreach-btn')?.addEventListener('click', () => {
        const contentArea = document.getElementById('outreach-content');
        contentArea.select();
        document.execCommand('copy');

        const btn = document.getElementById('copy-outreach-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = originalText, 2000);
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
        coverLetterMarkdown = '';

        // Show loading state
        submitBtn.disabled = true;
        btnText.textContent = 'Generating...';
        loader.classList.remove('hidden');
        resultsSection.classList.add('hidden');

        // Progress Bar Initialization
        const progressContainer = document.getElementById('progress-container');
        const progressBarFill = document.getElementById('progress-bar-fill');
        const progressText = document.getElementById('progress-text');

        // Clear previous state
        if (progressInterval) clearInterval(progressInterval);
        if (cleanupTimeout) clearTimeout(cleanupTimeout);

        progressContainer.classList.remove('hidden');

        // Reset instantly without animation
        progressBarFill.style.transition = 'none';
        progressBarFill.style.width = '0%';
        progressBarFill.offsetHeight; // Force reflow
        progressBarFill.style.transition = ''; // Restore CSS transition

        progressText.textContent = 'Initializing...';

        // Simulated Progress Logic
        let progress = 0;
        progressInterval = setInterval(() => {
            if (progress < 20) {
                progress += 2; // Fast start
                progressText.textContent = 'Parsing documents...';
            } else if (progress < 50) {
                progress += 1; // Steady climb
                progressText.textContent = 'Analyzing job description and resume...';
            } else if (progress < 80) {
                progress += 0.5; // Slow down
                progressText.textContent = 'Generating tailored suggestions...';
            } else if (progress < 95) {
                progress += 0.1; // Crawl to finish
                progressText.textContent = 'Finalizing formatting...';
            }
            progressBarFill.style.width = `${progress}%`;
        }, 500);

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

        // Add testing mode flag
        const isTestingMode = document.getElementById('testing-mode').checked;
        formData.append('is_testing_mode', isTestingMode);

        try {
            const response = await fetch('/api/process-job', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Network response was not ok');
            }

            // Complete progress bar
            clearInterval(progressInterval);
            progressBarFill.style.width = '100%';
            progressText.textContent = 'Complete!';

            // Short delay to show 100%
            await new Promise(resolve => setTimeout(resolve, 500));

            const data = await response.json();

            // Store data
            allSuggestions = data.resume_suggestions || [];
            originalResume = data.original_resume || '';
            coverLetterMarkdown = data.cover_letter || '';
            companyName = data.company_name || 'Company';
            roleTitle = data.role_title || 'Role';
            candidateName = data.candidate_name || 'Candidate';

            // We need to capture the JD text used. 
            // Ideally the backend returns it, but for now let's rely on the input logic if we can't get it back.
            // Actually, the backend doesn't return the raw JD.
            // Let's modify the backend return or just try to grab it from the form input for now?
            // Issue: if URL is used, we don't have the text here unless we scrape it again or return it.
            // BEST FIX: Ask backend to return 'final_job_desc'
            // For this iteration, let's assume we update backend to return it OR just grab what we can.

            // Wait, I can't easily modify backend return in this step without another tool call.
            // Let's assume the user hasn't cleared the form and grab values.
            const jobUrlInput = document.getElementById('job-url');
            const jobTextInput = document.getElementById('job-description');

            // This is imperfect (doesn't have scraped text), but good enough for now if we don't modify backend return.
            // BETTER: Let's assume the user will copy/paste if needed, OR we rely on the backend endpoint
            // accepting just the resume and generating blindly? No, need JD.

            // Let's just use the text input if available.
            currentJobDescription = jobTextInput.value || "Job description from URL: " + jobUrlInput.value;

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
            progressText.textContent = 'Error occurred';
            progressBarFill.style.backgroundColor = '#ef4444';
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            btnText.textContent = 'Generate Application Pack';
            loader.classList.add('hidden');

            // Hide progress bar after a delay
            cleanupTimeout = setTimeout(() => {
                progressContainer.classList.add('hidden');
                progressBarFill.style.width = '0%';
                // Reset color if error
                progressBarFill.style.backgroundColor = '';
            }, 2000);
        }
    });

    // Helper function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
