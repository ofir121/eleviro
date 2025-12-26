document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('job-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const loader = submitBtn.querySelector('.loader');
    const resultsSection = document.getElementById('results-section');

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

    // Download Logic
    document.querySelectorAll('.download-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const type = btn.dataset.type;
            let content = "";
            let filename = "document";

            if (type === 'resume') {
                content = document.getElementById('adapted-resume-content').textContent;
                filename = "Adapted_Resume";
            } else if (type === 'cover-letter') {
                content = document.getElementById('cover-letter-content').textContent;
                filename = "Cover_Letter";
            }

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
                    const url = window.URL.createObjectURL(blob);
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

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Show loading state
        submitBtn.disabled = true;
        btnText.textContent = 'Generating...';
        loader.classList.remove('hidden');
        resultsSection.classList.add('hidden');

        const formData = new FormData(form);

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

            // Populate results with Markdown rendering
            document.getElementById('job-summary-content').innerHTML = marked.parse(data.job_summary);
            document.getElementById('company-summary-content').innerHTML = marked.parse(data.company_summary);
            document.getElementById('adapted-resume-content').innerHTML = marked.parse(data.adapted_resume);
            document.getElementById('cover-letter-content').innerHTML = marked.parse(data.cover_letter);

            // Show results
            resultsSection.classList.remove('hidden');

            // Scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });

        } catch (error) {
            console.error('Error:', error);
            alert(error.message || 'An error occurred. Please check your inputs.');
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            btnText.textContent = 'Generate Application Pack';
            loader.classList.add('hidden');
        }
    });
});
