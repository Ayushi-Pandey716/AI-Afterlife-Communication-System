/**
 * chat.js — Training Accuracy Chat Display
 * Renders training steps and final accuracy as chat bubbles inside persona cards.
 */

class TrainingChat {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.lastStep = '';
    }

    /**
     * Append a chat bubble.
     * @param {string} text  - Message to display
     * @param {string} type  - 'ai' | 'system' | 'success' | 'error'
     */
    addMessage(text, type = 'ai') {
        if (!this.container) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'training-message-wrapper mb-2';

        const bubble = document.createElement('div');
        bubble.className = `training-bubble training-bubble-${type} p-2 px-3`;
        bubble.innerHTML = this._icon(type) + text;

        wrapper.appendChild(bubble);
        this.container.appendChild(wrapper);
        this.scrollToBottom();
    }

    /**
     * Append a formatted accuracy results bubble with confusion matrices.
     * @param {object} accuracyData
     */
    addAccuracy(accuracyData) {
        if (!this.container) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'training-message-wrapper mb-2';

        const bubble = document.createElement('div');
        bubble.className = 'training-bubble training-bubble-accuracy p-3';

        let html = `<div class="accuracy-title"><i class="fas fa-chart-bar me-2"></i><strong>Training Complete! Accuracy Report</strong></div><hr class="my-2">`;

        if (accuracyData.whatsapp_accuracy !== undefined) {
            const wa = Math.round(accuracyData.whatsapp_accuracy);
            html += `
                <div class="accuracy-row">
                    <span><i class="fas fa-comments me-1"></i> WhatsApp Chat</span>
                    <span class="ms-auto d-flex align-items-center gap-2">
                        <div class="mini-progress-bar">
                            <div class="mini-progress-fill" style="width:${wa}%"></div>
                        </div>
                        <strong>${wa}%</strong>
                    </span>
                </div>`;
            if (accuracyData.whatsapp_confusion_matrix) {
                html += this._cmTable(accuracyData.whatsapp_confusion_matrix);
            }
        }

        if (accuracyData.voice_accuracy !== undefined) {
            const va = Math.round(accuracyData.voice_accuracy);
            html += `
                <div class="accuracy-row mt-2">
                    <span><i class="fas fa-microphone me-1"></i> Voice Recording</span>
                    <span class="ms-auto d-flex align-items-center gap-2">
                        <div class="mini-progress-bar">
                            <div class="mini-progress-fill" style="width:${va}%"></div>
                        </div>
                        <strong>${va}%</strong>
                    </span>
                </div>`;
            if (accuracyData.voice_confusion_matrix) {
                html += this._cmTable(accuracyData.voice_confusion_matrix);
            }
        }

        if (accuracyData.overall_accuracy !== undefined) {
            const oa = Math.round(accuracyData.overall_accuracy);
            html += `
                <div class="accuracy-row overall-row mt-2 pt-2">
                    <span><i class="fas fa-brain me-1"></i> <strong>Overall Accuracy</strong></span>
                    <span class="ms-auto"><strong class="accuracy-percent">${oa}%</strong></span>
                </div>`;
        }

        if (accuracyData.messages_analyzed) {
            html += `<div class="accuracy-detail mt-1"><small><i class="fas fa-envelope me-1"></i>${accuracyData.messages_analyzed} messages analysed</small></div>`;
        }
        if (accuracyData.voice_features) {
            html += `<div class="accuracy-detail"><small><i class="fas fa-wave-square me-1"></i>${accuracyData.voice_features} voice features extracted</small></div>`;
        }

        bubble.innerHTML = html;
        wrapper.appendChild(bubble);
        this.container.appendChild(wrapper);
        this.scrollToBottom();
    }

    /**
     * Render a 2×2 confusion matrix grid.
     * Returns an HTML string, or '' if no data.
     * @param {object} cm  - {TP, TN, FP, FN}
     */
    _cmTable(cm) {
        if (!cm || (cm.TP === 0 && cm.TN === 0 && cm.FP === 0 && cm.FN === 0)) return '';
        return `
            <div class="cm-table mt-2 mb-1">
                <div class="cm-header"></div>
                <div class="cm-header">Pred +</div>
                <div class="cm-header">Pred −</div>
                <div class="cm-label">Actual +</div>
                <div class="cm-cell cm-tp">TP<br><span class="cm-val">${cm.TP}</span></div>
                <div class="cm-cell cm-fn">FN<br><span class="cm-val">${cm.FN}</span></div>
                <div class="cm-label">Actual −</div>
                <div class="cm-cell cm-fp">FP<br><span class="cm-val">${cm.FP}</span></div>
                <div class="cm-cell cm-tn">TN<br><span class="cm-val">${cm.TN}</span></div>
            </div>`;
    }

    clear() {
        if (this.container) this.container.innerHTML = '';
        this.lastStep = '';
    }

    scrollToBottom() {
        if (this.container) {
            this.container.scrollTop = this.container.scrollHeight;
        }
    }

    _icon(type) {
        const icons = {
            ai: '<i class="fas fa-robot me-2"></i>',
            system: '<i class="fas fa-cog fa-spin me-2"></i>',
            success: '<i class="fas fa-check-circle me-2 text-success"></i>',
            error: '<i class="fas fa-times-circle me-2 text-danger"></i>',
            accuracy: '<i class="fas fa-chart-bar me-2"></i>',
        };
        return icons[type] || icons.ai;
    }
}

/**
 * Poll training progress and render steps as chat bubbles.
 * @param {number} personaId
 * @param {string} csrfToken
 * @param {string} chatContainerId
 */
function pollTrainingProgress(personaId, csrfToken, chatContainerId) {
    const chat = new TrainingChat(chatContainerId);
    chat.clear();
    chat.addMessage('Training started! Sit tight while I learn about this persona…', 'ai');

    const interval = setInterval(() => {
        fetch(`/training-progress/${personaId}/`)
            .then(res => res.json())
            .then(data => {
                // Render new step message if changed
                if (data.step_message && data.step_message !== chat.lastStep) {
                    chat.addMessage(data.step_message, 'system');
                    chat.lastStep = data.step_message;
                }

                // Update progress bar if present
                const bar = document.getElementById('training-progress-bar');
                const pct = document.getElementById('training-progress-pct');
                if (bar) bar.style.width = data.progress + '%';
                if (pct) pct.textContent = data.progress + '%';

                if (data.status === 'completed') {
                    clearInterval(interval);
                    chat.addMessage('All done! Calculating accuracy…', 'ai');

                    // Show accuracy if available
                    if (data.accuracy && Object.keys(data.accuracy).length > 0) {
                        chat.addAccuracy(data.accuracy);
                    } else {
                        chat.addMessage('Training completed successfully! The persona is ready to chat.', 'success');
                    }

                    // Fade in the results, then reload after delay
                    setTimeout(() => { window.location.reload(); }, 3000);
                }

                if (data.status === 'failed') {
                    clearInterval(interval);
                    chat.addMessage('Training failed. Please try again.', 'error');

                    // Re-enable start button
                    const btn = document.getElementById('start-training-btn');
                    if (btn) {
                        btn.innerHTML = '<i class="fas fa-redo"></i> Retry Training';
                        btn.disabled = false;
                    }
                }
            })
            .catch(err => {
                console.error('Polling error:', err);
                clearInterval(interval);
                const chat2 = new TrainingChat(chatContainerId);
                chat2.addMessage('Connection error during training. Check your network.', 'error');
            });
    }, 2000);
}

/**
 * Start training and kick off chat polling.
 * Called from upload.html
 */
function startTrainingWithChat(personaId, csrfToken, chatContainerId) {
    const btn = document.getElementById('start-training-btn');
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting…';
        btn.disabled = true;
    }

    // Show chat container
    const chatSection = document.getElementById('training-chat-section');
    if (chatSection) chatSection.classList.remove('d-none');

    fetch(`/train/${personaId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json',
        },
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            pollTrainingProgress(personaId, csrfToken, chatContainerId);
        } else {
            const chat = new TrainingChat(chatContainerId);
            chat.addMessage('Failed to start training: ' + (data.error || 'Unknown error'), 'error');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-play"></i> Start Training';
                btn.disabled = false;
            }
        }
    })
    .catch(err => {
        console.error(err);
        if (btn) {
            btn.innerHTML = '<i class="fas fa-play"></i> Start Training';
            btn.disabled = false;
        }
    });
}
