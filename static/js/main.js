/**
 * Campus Lost & Found System - Client Interactive Script
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });

    // 2. Image upload preview
    const imageInput = document.getElementById('imageUploadInput');
    const imagePreview = document.getElementById('imagePreviewTarget');
    if (imageInput && imagePreview) {
        imageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(evt) {
                    imagePreview.src = evt.target.result;
                    imagePreview.classList.remove('d-none');
                    const placeholderBox = document.getElementById('uploadPlaceholderBox');
                    if (placeholderBox) placeholderBox.classList.add('d-none');
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // 3. Dynamic Toggle for Found Item custody field
    const itemTypeSelect = document.getElementById('itemTypeSelect');
    const storageLocationGroup = document.getElementById('storageLocationGroup');
    if (itemTypeSelect && storageLocationGroup) {
        const toggleStorageField = () => {
            if (itemTypeSelect.value === 'found') {
                storageLocationGroup.classList.remove('d-none');
            } else {
                storageLocationGroup.classList.add('d-none');
            }
        };
        itemTypeSelect.addEventListener('change', toggleStorageField);
        toggleStorageField();
    }

    // 4. Quick Copy Token helper
    window.copyToClipboard = function(text, btnElement) {
        if (!navigator.clipboard) {
            fallbackCopy(text);
            return;
        }
        navigator.clipboard.writeText(text).then(() => {
            const originalHTML = btnElement.innerHTML;
            btnElement.innerHTML = '<i class="bi bi-check2"></i> Copied!';
            btnElement.classList.add('btn-success');
            setTimeout(() => {
                btnElement.innerHTML = originalHTML;
                btnElement.classList.remove('btn-success');
            }, 2000);
        });
    };

    function fallbackCopy(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        alert('Copied to clipboard: ' + text);
    }

    // 5. Client validation for date (max today)
    const dateInput = document.getElementById('eventDateInput');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.setAttribute('max', today);
    }

    // ---------------------------------------------------------
    // 6. CampusBot AI Assistant Controller
    // ---------------------------------------------------------
    const botToggle = document.getElementById('campusBotToggle');
    const botPanel = document.getElementById('campusBotPanel');
    const botClose = document.getElementById('campusBotClose');
    const botMessages = document.getElementById('campusBotMessages');
    const botInput = document.getElementById('campusBotInput');
    const botSend = document.getElementById('campusBotSend');

    if (botToggle && botPanel) {
        const toggleBot = () => {
            botPanel.classList.toggle('d-none');
            if (!botPanel.classList.contains('d-none')) {
                botInput.focus();
                // Send initial greeting if empty
                if (botMessages.children.length === 0) {
                    sendBotMessage('');
                }
            }
        };

        botToggle.addEventListener('click', toggleBot);
        if (botClose) botClose.addEventListener('click', () => botPanel.classList.add('d-none'));

        function appendMessage(text, sender = 'bot', items = [], quickReplies = []) {
            const bubble = document.createElement('div');
            bubble.className = `chat-bubble chat-bubble-${sender}`;

            // Format markdown bold and newlines
            let formatted = text
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/\n/g, '<br>');

            bubble.innerHTML = formatted;

            // Render item cards if any
            if (items && items.length > 0) {
                items.forEach(itm => {
                    const card = document.createElement('a');
                    card.href = `/items/${itm.id}`;
                    card.className = 'chat-item-card';
                    card.innerHTML = `
                        <div class="rounded bg-light p-1 border text-center" style="width: 44px; height: 44px; flex-shrink: 0;">
                            <i class="bi ${itm.type === 'found' ? 'bi-box-seam text-success' : 'bi-question-circle text-danger'} fs-4"></i>
                        </div>
                        <div class="flex-grow-1 overflow-hidden">
                            <div class="fw-bold text-truncate text-dark small">${itm.title}</div>
                            <div class="text-muted text-truncate" style="font-size: 0.72rem;">
                                <i class="bi bi-geo-alt me-1"></i>${itm.location || 'Campus'} &bull; ${itm.event_date || ''}
                            </div>
                        </div>
                        <span class="badge ${itm.type === 'found' ? 'bg-success' : 'bg-danger'} text-capitalize ms-auto" style="font-size: 0.65rem;">
                            ${itm.type}
                        </span>
                    `;
                    bubble.appendChild(card);
                });
            }

            // Render quick replies if any
            if (quickReplies && quickReplies.length > 0) {
                const qrContainer = document.createElement('div');
                qrContainer.className = 'chat-quick-replies';
                quickReplies.forEach(qr => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'quick-reply-btn';
                    btn.textContent = qr;
                    btn.addEventListener('click', () => {
                        botInput.value = qr;
                        sendBotMessage(qr);
                    });
                    qrContainer.appendChild(btn);
                });
                bubble.appendChild(qrContainer);
            }

            botMessages.appendChild(bubble);
            botMessages.scrollTop = botMessages.scrollHeight;
        }

        async function sendBotMessage(msg) {
            if (msg.trim()) {
                appendMessage(msg, 'user');
                botInput.value = '';
            }

            // Typing indicator
            const typingBubble = document.createElement('div');
            typingBubble.className = 'chat-bubble chat-bubble-bot text-muted';
            typingBubble.id = 'botTypingIndicator';
            typingBubble.innerHTML = '<span class="spinner-grow spinner-grow-sm me-1" role="status"></span> <em>CampusBot is thinking...</em>';
            botMessages.appendChild(typingBubble);
            botMessages.scrollTop = botMessages.scrollHeight;

            try {
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                });
                const data = await resp.json();
                const indicator = document.getElementById('botTypingIndicator');
                if (indicator) indicator.remove();

                appendMessage(data.text || "I'm here to help you navigate campus lost & found.", 'bot', data.items || [], data.quick_replies || []);
            } catch (err) {
                const indicator = document.getElementById('botTypingIndicator');
                if (indicator) indicator.remove();
                appendMessage("I couldn't reach the campus server at this second. Please try again or visit Campus Security Desk.", 'bot');
            }
        }

        if (botSend) {
            botSend.addEventListener('click', () => {
                const txt = botInput.value.trim();
                if (txt) sendBotMessage(txt);
            });
        }

        if (botInput) {
            botInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const txt = botInput.value.trim();
                    if (txt) sendBotMessage(txt);
                }
            });
        }
    }

    // ---------------------------------------------------------
    // 7. Real-Time Notification Poller & Live Toasts
    // ---------------------------------------------------------
    const notifBadge = document.getElementById('notificationCountBadge');
    const toastContainer = document.getElementById('liveToastContainer');
    let knownNotifIds = new Set();
    let initialPoll = true;

    async function pollNotifications() {
        try {
            const resp = await fetch('/api/notifications/poll');
            const data = await resp.json();
            if (!data.logged_in) return;

            // Update badge count
            if (notifBadge) {
                if (data.unread_count > 0) {
                    notifBadge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                    notifBadge.classList.remove('d-none');
                } else {
                    notifBadge.classList.add('d-none');
                }
            }

            // Check for new notifications to toast
            if (data.notifications && toastContainer) {
                data.notifications.forEach(notif => {
                    if (!knownNotifIds.has(notif.id)) {
                        knownNotifIds.add(notif.id);

                        // Don't toast existing unread items on first page load
                        if (!initialPoll) {
                            showNotificationToast(notif);
                        }
                    }
                });
            }
            initialPoll = false;
        } catch (e) {
            // Silently ignore poll network drops
        }
    }

    function showNotificationToast(notif) {
        if (!toastContainer) return;
        const toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center text-bg-dark border-0 shadow-lg mb-2';
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = `
            <div class="toast-header bg-dark text-white border-secondary border-opacity-25">
                <i class="bi bi-bell-fill text-warning me-2"></i>
                <strong class="me-auto">${notif.title}</strong>
                <small class="text-white-50">Just now</small>
                <button type="button" class="btn-close btn-close-white ms-2" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body bg-dark text-light">
                <p class="small mb-2">${notif.message}</p>
                <div class="d-flex justify-content-end">
                    <a href="${notif.link || '/notifications'}" class="btn btn-primary btn-sm py-1 px-3 rounded-pill">
                        View Details <i class="bi bi-arrow-right ms-1"></i>
                    </a>
                </div>
            </div>
        `;
        toastContainer.appendChild(toastEl);
        const bsToast = new bootstrap.Toast(toastEl, { delay: 7000 });
        bsToast.show();
    }

    // Run poll if user is logged in
    if (notifBadge) {
        pollNotifications();
        setInterval(pollNotifications, 12000); // Poll every 12s
    }
});
