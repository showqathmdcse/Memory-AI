let isWaiting = false;
let currentChatId = 'default';
let chats = {};
let currentMessages = {};

// SSE Configuration
const SSE_CONFIG = {
    sseUrl: `${window.location.origin}/sse/agent`,
    backendUrl: window.location.origin
};

// SSE State
let sseConnection = null;
let isSseConnected = false;
let currentStreamingMessage = null;
// Some backends send BOTH streaming tokens AND a final full "response" message.
// If we render tokens live, we must NOT overwrite the UI with that final response
// (it often contains placeholders like CODEBLOCK0). This flag tracks whether we've
// already received any tokens for the current stream.
let hasReceivedStreamTokens = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    const userInput = document.getElementById('userInput');
    
    // Load theme preference
    loadTheme();
    
    // Load chats from localStorage
    loadChats();
    
    // Initialize current chat
    if (!currentChatId || !chats[currentChatId]) {
        currentChatId = 'default';
        if (!chats[currentChatId]) {
            chats[currentChatId] = {
                id: 'default',
                title: 'New Chat',
                preview: '',
                timestamp: Date.now()
            };
        }
    }
    
    // Render chat list
    renderChatList();
    switchToChat(currentChatId);
    
    // Connect to SSE
    connectToSSE();
    
    // Allow Enter key to send message (Shift+Enter for new line)
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey && !isWaiting) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Toggle send button visibility and auto-resize textarea
    userInput.addEventListener('input', function() {
        toggleSendButton();
        autoResizeTextarea(this);
    });
    
    // Focus on input field
    userInput.focus();
});

// Connect to SSE
function connectToSSE() {
    try {
        const sseUrl = `${SSE_CONFIG.sseUrl}?chatId=${currentChatId}`;
        console.log('Connecting to SSE at:', sseUrl);
        
        sseConnection = new EventSource(sseUrl);
        
        sseConnection.addEventListener('connected', (event) => {
            isSseConnected = true;
            console.log('✅ Connected to SSE successfully:', event.data);
        });
        
        sseConnection.addEventListener('message', (event) => {
            try {
                const data = JSON.parse(event.data);
                handleStreamMessage(data);
            } catch (error) {
                console.error('Error parsing SSE message:', error);
            }
        });
        
        sseConnection.onerror = (error) => {
            console.error('SSE error:', error);
            isSseConnected = false;
            sseConnection.close();
            
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                console.log('Attempting to reconnect to SSE...');
                connectToSSE();
            }, 3000);
        };
        
    } catch (error) {
        console.error('Failed to connect to SSE:', error);
        console.log('⚠️ SSE not available - using HTTP fallback only');
        isSseConnected = false;
    }
}

// Handle incoming streaming messages from WebSocket
function handleStreamMessage(data) {
    console.log('📨 NATS Message:', data);
    
    // Only handle messages for current chat
    if (data.chat_id && data.chat_id !== currentChatId) {
        return;
    }

    // Handle both 'type' and 'message_type' fields (for compatibility)
    const messageType = data.type || data.message_type;
    
    switch (messageType) {
        case 'start':
            handleStreamStart(data);
            break;

        case 'token':
        case 'chunk':
            handleStreamingToken(data);
            break;

        case 'response':
            handleStreamResponse(data);
            break;

        case 'end':
            handleStreamEnd(data);
            break;

        case 'error':
            handleStreamError(data);
            break;

        case 'tool':
            handleToolUsage(data);
            break;
            
        case 'thinking':
            handleThinking(data);
            break;

        default:
            console.log('Unknown message type:', messageType);
    }
}

// Handle stream start
function handleStreamStart(data) {
    console.log('🚀 Stream started');
    
    // Show typing indicator if not already visible
    if (!document.getElementById('typingIndicator')) {
        showTypingIndicator();
    }
    
    // Prepare for streaming message
    currentStreamingMessage = null;
    hasReceivedStreamTokens = false;
}

// Handle streaming token/chunk (real-time token-by-token display)
function handleStreamingToken(data) {
    console.log('💬 Chunk/Token received:', data.content);

    hasReceivedStreamTokens = true;
    
    // Remove typing indicator on first token
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        console.log('Removing typing indicator');
        typingIndicator.remove();
    }
    
    // Extract the chunk text - support multiple formats
    const token = data.content.chunk || data.content.content || data.content;
    console.log('Extracted token:', token);
    
    // Create streaming message on first token
    if (!currentStreamingMessage) {
        console.log('Creating new streaming message');
        const assistantTime = getCurrentTime();
        currentStreamingMessage = createStreamingMessage('assistant', assistantTime);
        console.log('Streaming message created:', currentStreamingMessage);
    }
    
    // Append token/chunk to streaming message with live formatting
    console.log('Appending token to message');
    appendTokenToMessageWithFormatting(currentStreamingMessage, token);
}

// Create a new streaming message element
function createStreamingMessage(sender, time) {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.id = 'streaming-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.id = 'streaming-content';
    contentDiv.textContent = ''; // Start with empty content
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = time;
    
    contentDiv.appendChild(timeDiv);
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    return messageDiv;
}

// Append a token to the streaming message with live formatting
function appendTokenToMessageWithFormatting(messageDiv, token) {
    console.log('appendTokenToMessageWithFormatting called with token:', token);
    const contentDiv = messageDiv.querySelector('#streaming-content');
    console.log('contentDiv found:', contentDiv);
    
    if (contentDiv) {
        // Get current text (excluding the time element)
        const timeElement = contentDiv.querySelector('.message-time');
        
        // Get current plain text content
        let currentText = '';
        if (contentDiv.dataset.plainText) {
            currentText = contentDiv.dataset.plainText;
        }
        
        // Append new token
        const newText = currentText + token;
        console.log('New accumulated text:', newText.substring(0, 50) + '...');
        
        // Store plain text for next iteration
        contentDiv.dataset.plainText = newText;
        
        // Apply markdown formatting in real-time
        const formattedText = formatMessageWithCodeBlocks(newText);
        contentDiv.innerHTML = formattedText;
        contentDiv.appendChild(timeElement);
        console.log('UI updated with formatted text');
        
        // Auto-scroll to bottom
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.scrollTop = chatContainer.scrollHeight;
    } else {
        console.error('❌ contentDiv not found!');
    }
}

// Handle stream response (actual agent reply) with typing effect
function handleStreamResponse(data) {
    console.log('💬 Agent response:', data.content);

    // If we are already rendering token-by-token, do NOT overwrite the message with
    // the backend's full response payload.
    if (hasReceivedStreamTokens) {
        console.log('Skipping full response message because token streaming is active');
        return;
    }
    
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
    
    // Get the response text
    const responseText = data.content.reply || data.content.response || data.content;
    
    // Simulate typing effect
    const assistantTime = getCurrentTime();
    simulateTypingEffect(responseText, assistantTime);
}

// Simulate typing effect (displays text character by character with live formatting)
async function simulateTypingEffect(text, time) {
    // Create streaming message element
    if (!currentStreamingMessage) {
        currentStreamingMessage = createStreamingMessage('assistant', time);
    }
    
    const contentDiv = currentStreamingMessage.querySelector('#streaming-content');
    const timeElement = contentDiv.querySelector('.message-time');
    
    // Type out the message character by character with live markdown formatting
    let displayedText = '';
    const typingSpeed = 10; // milliseconds per character (faster)
    
    for (let i = 0; i < text.length; i++) {
        displayedText += text[i];
        
        // Apply markdown formatting in real-time during typing
        const formattedText = formatMessageWithCodeBlocks(displayedText);
        contentDiv.innerHTML = formattedText;
        contentDiv.appendChild(timeElement);
        
        // Auto-scroll
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        // Wait before showing next character
        await new Promise(resolve => setTimeout(resolve, typingSpeed));
    }
    
    // Save the complete message
    storeMessage(text, 'assistant', time);
    
    // Clean up
    currentStreamingMessage.id = '';
    currentStreamingMessage = null;
    
    // Re-enable input
    isWaiting = false;
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    userInput.disabled = false;
    sendButton.disabled = false;
    toggleSendButton();
    userInput.focus();
}

// Handle stream end
function handleStreamEnd(data) {
    console.log('✅ Stream ended');
    
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
    
    // Finalize and save streaming message
    if (currentStreamingMessage) {
        const contentDiv = currentStreamingMessage.querySelector('#streaming-content');
        if (contentDiv) {
            // Get the accumulated plain text we've been storing
            const finalText = contentDiv.dataset.plainText || '';
            const timeElement = contentDiv.querySelector('.message-time');
            
            // Store the complete message
            const assistantTime = timeElement ? timeElement.textContent : getCurrentTime();
            if (finalText) {
                storeMessage(finalText, 'assistant', assistantTime);
            }
            
            // Remove streaming ID
            currentStreamingMessage.id = '';
            currentStreamingMessage = null;
        }
    }
    
    // Re-enable input
    isWaiting = false;
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    userInput.disabled = false;
    sendButton.disabled = false;
    toggleSendButton();
    userInput.focus();
}

// Handle stream error
function handleStreamError(data) {
    console.error('❌ Stream error:', data.content);
    
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
    
    const errorMessage = data.content.error || 'An error occurred';
    const errorTime = getCurrentTime();
    addMessage(`Error: ${errorMessage}`, 'assistant', errorTime, true);
    
    isWaiting = false;
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    userInput.disabled = false;
    sendButton.disabled = false;
    toggleSendButton();
}

// Handle tool usage
function handleToolUsage(data) {
    console.log('🔧 Tool usage:', data.content);
    
    const toolName = data.content.tool_name || data.content.name || 'unknown';
    const toolAction = data.content.action || 'using';
    
    // Show tool usage indicator
    addThinkingMessage(`🔧 ${toolAction} tool: ${toolName}`);
}

// Handle thinking updates
function handleThinking(data) {
    console.log('💭 Thinking:', data.content);
    
    const thinkingText = data.content.message || data.content || 'Processing...';
    addThinkingMessage(`💭 ${thinkingText}`);
}

// Add a thinking/status message
function addThinkingMessage(text) {
    const chatContainer = document.getElementById('chatContainer');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant thinking-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.style.background = 'rgba(102, 126, 234, 0.1)';
    contentDiv.style.border = '1px solid rgba(102, 126, 234, 0.3)';
    contentDiv.style.fontStyle = 'italic';
    contentDiv.style.fontSize = '0.9em';
    contentDiv.textContent = text;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();
    
    contentDiv.appendChild(timeDiv);
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function autoResizeTextarea(textarea) {
    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';
    
    // Set the height to match content, with max height constraint
    const maxHeight = 200; // matches max-height in CSS
    const newHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = newHeight + 'px';
}

function toggleSendButton() {
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const attachmentBtn = document.getElementById('attachmentBtn');
    
    if (userInput.value.trim()) {
        sendButton.style.display = 'flex';
        attachmentBtn.style.display = 'none';
    } else {
        sendButton.style.display = 'none';
        attachmentBtn.style.display = 'flex';
    }
}

function loadChats() {
    const stored = localStorage.getItem('memoryai_chats');
    if (stored) {
        chats = JSON.parse(stored);
    } else {
        chats = {
            'default': {
                id: 'default',
                title: 'New Chat',
                preview: '',
                timestamp: Date.now()
            }
        };
    }
    
    const storedMessages = localStorage.getItem('memoryai_messages');
    if (storedMessages) {
        currentMessages = JSON.parse(storedMessages);
    }
}

function saveChats() {
    localStorage.setItem('memoryai_chats', JSON.stringify(chats));
    localStorage.setItem('memoryai_messages', JSON.stringify(currentMessages));
}

function generateChatId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function createNewChat() {
    const newChatId = generateChatId();
    chats[newChatId] = {
        id: newChatId,
        title: 'New Chat',
        preview: '',
        timestamp: Date.now()
    };
    currentMessages[newChatId] = [];
    saveChats();
    renderChatList();
    switchToChat(newChatId);
}

function switchToChat(chatId) {
    currentChatId = chatId;
    
    // Update active state in sidebar
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.chatId === chatId) {
            item.classList.add('active');
        }
    });
    
    // Clear and load messages for this chat
    loadChatMessages(chatId);
    
    saveChats();
}

function loadChatMessages(chatId) {
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = '';
    
    const messages = currentMessages[chatId] || [];
    
    if (messages.length === 0) {
        showWelcomeMessage();
        showSuggestions();
    } else {
        messages.forEach(msg => {
            addMessageToUI(msg.text, msg.sender, msg.time);
        });
        hideSuggestions();
    }
}

// Array of suggestion messages with their icons
const suggestionMessages = [
    { text: "Your Knowledge. My Intelligence. Our Solutions.", icon: "💡" },
    { text: "Powered by AI. Driven by Your Questions.", icon: "⚡" },
    { text: "Ask Anything. Solve Everything.", icon: "🎯" },
    { text: "Smart Conversations. Real Results.", icon: "💬" },
    { text: "Think. Plan. Execute. Together.", icon: "🚀" },
    { text: "Your AI Dev Partner — Always Ready.", icon: "👨‍💻" },
    { text: "Code smarter, not harder.", icon: "⚙️" },
    { text: "Talk to me like a developer.", icon: "🔧" },
    { text: "Hi! I'm your AI assistant — ask me anything.", icon: "👋" },
    { text: "Let's build something amazing together.", icon: "🌟" },
    { text: "Your ideas, my intelligence.", icon: "🧠" },
    { text: "Your Tools. My Brain. Full Automation.", icon: "🤖" },
    { text: "One Agent. All your MCP skills unlocked.", icon: "🔓" },
    { text: "I think. I reason. I run your tools.", icon: "🎲" },
    { text: "Ask. Learn. Create.", icon: "✨" },
    { text: "AI that works with you.", icon: "🤝" },
    { text: "Fast. Smart. Helpful.", icon: "⚡" }
];

function showSuggestions() {
    const suggestionsContainer = document.getElementById('suggestionsContainer');
    const suggestionMessage = document.getElementById('suggestionMessage');
    const suggestionIcon = document.getElementById('suggestionIcon');
    
    if (suggestionsContainer && suggestionMessage && suggestionIcon) {
        // Pick a random message
        const randomSuggestion = suggestionMessages[Math.floor(Math.random() * suggestionMessages.length)];
        suggestionMessage.textContent = randomSuggestion.text;
        suggestionIcon.textContent = randomSuggestion.icon;
        suggestionsContainer.style.display = 'block';
    }
}

function hideSuggestions() {
    const suggestionsContainer = document.getElementById('suggestionsContainer');
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'none';
    }
}

function showWelcomeMessage() {
    const chatContainer = document.getElementById('chatContainer');
    const welcomeMessage = document.createElement('div');
    welcomeMessage.className = 'welcome-message';
    welcomeMessage.innerHTML = `
        <div class="welcome-icon">🧠</div>
        <h2>Welcome to MemoryAI!</h2>
        <p>I'm an AI assistant with perfect conversational memory. I remember everything you tell me across our conversations!</p>
    `;
    chatContainer.appendChild(welcomeMessage);
}

function renderChatList() {
    const chatList = document.getElementById('chatList');
    chatList.innerHTML = '';
    
    // Sort chats by timestamp (newest first)
    const sortedChats = Object.values(chats).sort((a, b) => b.timestamp - a.timestamp);
    
    sortedChats.forEach(chat => {
        const chatItem = document.createElement('div');
        chatItem.className = 'chat-item';
        if (chat.id === currentChatId) {
            chatItem.classList.add('active');
        }
        chatItem.dataset.chatId = chat.id;
        chatItem.onclick = () => switchToChat(chat.id);
        
        chatItem.innerHTML = `
            <div class="chat-item-content">
                <div class="chat-item-title">${chat.title}</div>
            </div>
            <div class="chat-item-actions">
                <button class="chat-item-btn" onclick="event.stopPropagation(); deleteChat('${chat.id}')" title="Delete chat">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
                    </svg>
                </button>
            </div>
        `;
        
        chatList.appendChild(chatItem);
    });
}

function deleteChat(chatId) {
    showModal(
        'Delete Chat',
        'Are you sure you want to delete this chat? The conversation will be permanently removed from your device.',
        'Delete',
        'Cancel',
        () => {
            delete chats[chatId];
            delete currentMessages[chatId];
            
            // If we deleted the current chat or if there are no chats left, create/switch to a new one
            const remainingChats = Object.keys(chats);
            if (remainingChats.length === 0 || currentChatId === chatId) {
                // Create a new default chat if no chats remain
                if (remainingChats.length === 0) {
                    chats['default'] = {
                        id: 'default',
                        title: 'New Chat',
                        preview: '',
                        timestamp: Date.now()
                    };
                    currentMessages['default'] = [];
                    switchToChat('default');
                } else {
                    // Switch to the first remaining chat
                    switchToChat(remainingChats[0]);
                }
            }
            
            saveChats();
            renderChatList();
        }
    );
}

function clearCurrentChat() {
    showModal(
        'Clear Messages',
        'Are you sure you want to clear all messages in this chat? The conversation history in memory will be preserved.',
        'Clear',
        'Cancel',
        () => {
            currentMessages[currentChatId] = [];
            saveChats();
            loadChatMessages(currentChatId);
        }
    );
}

function showModal(title, message, confirmText, cancelText, onConfirm) {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-header">
            <h3>${title}</h3>
        </div>
        <div class="modal-body">
            <p>${message}</p>
        </div>
        <div class="modal-footer">
            <button class="modal-btn modal-btn-cancel" id="modalCancel">${cancelText}</button>
            <button class="modal-btn modal-btn-confirm" id="modalConfirm">${confirmText}</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Add animation
    setTimeout(() => {
        overlay.classList.add('show');
    }, 10);
    
    // Event handlers
    const closeModal = () => {
        overlay.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(overlay);
        }, 200);
    };
    
    document.getElementById('modalCancel').onclick = closeModal;
    document.getElementById('modalConfirm').onclick = () => {
        closeModal();
        onConfirm();
    };
    
    // Close on overlay click
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            closeModal();
        }
    };
    
    // Focus confirm button
    document.getElementById('modalConfirm').focus();
}

function showAlert(title, message) {
    showModal(title, message, 'OK', null, () => {});
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}

function toggleTheme() {
    const body = document.body;
    const sunIcon = document.querySelector('.sun-icon');
    const moonIcon = document.querySelector('.moon-icon');
    
    body.classList.toggle('light-theme');
    
    if (body.classList.contains('light-theme')) {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
        localStorage.setItem('memoryai_theme', 'light');
    } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
        localStorage.setItem('memoryai_theme', 'dark');
    }
}

function loadTheme() {
    const savedTheme = localStorage.getItem('memoryai_theme');
    const body = document.body;
    const sunIcon = document.querySelector('.sun-icon');
    const moonIcon = document.querySelector('.moon-icon');
    
    if (savedTheme === 'light') {
        body.classList.add('light-theme');
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
    } else {
        body.classList.remove('light-theme');
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
    }
}

function toggleUserMenu() {
    const userMenu = document.getElementById('userMenu');
    userMenu.classList.toggle('show');
    
    // Close menu when clicking outside
    if (userMenu.classList.contains('show')) {
        setTimeout(() => {
            document.addEventListener('click', closeUserMenuOnClickOutside);
        }, 0);
    }
}

function closeUserMenuOnClickOutside(event) {
    const userMenu = document.getElementById('userMenu');
    const userMenuBtn = document.querySelector('.user-menu-btn');
    
    if (!userMenu.contains(event.target) && !userMenuBtn.contains(event.target)) {
        userMenu.classList.remove('show');
        document.removeEventListener('click', closeUserMenuOnClickOutside);
    }
}

async function sendMessage() {
    const userInput = document.getElementById('userInput');
    const userId = document.getElementById('userId').value.trim();
    const message = userInput.value.trim();
    const sendButton = document.getElementById('sendButton');
    const chatContainer = document.getElementById('chatContainer');
    
    // Validation
    if (!message) {
        return;
    }
    
    if (!userId) {
        showAlert('User ID Required', 'Please enter a User ID to continue.');
        return;
    }
    
    // Clear welcome message if it exists
    const welcomeMessage = chatContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
    
    // Hide suggestions after first message
    hideSuggestions();
    
    // Add user message to chat
    const userTime = getCurrentTime();
    addMessage(message, 'user', userTime);
    storeMessage(message, 'user', userTime);
    
    // Update chat title and preview if this is the first message
    if (!chats[currentChatId].preview) {
        chats[currentChatId].title = message.substring(0, 30) + (message.length > 30 ? '...' : '');
        chats[currentChatId].preview = message.substring(0, 50) + (message.length > 50 ? '...' : '');
        chats[currentChatId].timestamp = Date.now();
        saveChats();
        renderChatList();
    }
    
    // Clear input and reset height
    userInput.value = '';
    userInput.style.height = 'auto';
    toggleSendButton();
    
    // Disable input while waiting
    isWaiting = true;
    userInput.disabled = true;
    sendButton.disabled = true;
    
    // Show typing indicator (will be removed by NATS handler or on error)
    showTypingIndicator();
    
    try {
        // Send message to backend
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                chat_id: currentChatId,
                message: message
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // If SSE is NOT connected, handle response directly (fallback mode)
        if (!isSseConnected) {
            console.log('📡 SSE not connected - using HTTP fallback');
            
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            
            // Add assistant response
            const assistantTime = getCurrentTime();
            addMessage(data.reply, 'assistant', assistantTime);
            storeMessage(data.reply, 'assistant', assistantTime);
            
            // Re-enable input
            isWaiting = false;
            userInput.disabled = false;
            sendButton.disabled = false;
            toggleSendButton();
            userInput.focus();
        } else {
            // SSE is connected - response will come via SSE streaming
            console.log('✅ Message sent - waiting for SSE stream...');
            // The stream handlers (handleStreamResponse, handleStreamEnd) will:
            // - Remove the typing indicator
            // - Add the assistant message
            // - Re-enable the input
        }
        
    } catch (error) {
        console.error('Error:', error);
        
        // Remove typing indicator
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
        
        // Show error message
        const errorTime = getCurrentTime();
        addMessage('Sorry, I encountered an error. Please try again.', 'assistant', errorTime, true);
        
        // Re-enable input
        isWaiting = false;
        userInput.disabled = false;
        sendButton.disabled = false;
        toggleSendButton();
        userInput.focus();
    }
}

function storeMessage(text, sender, time) {
    if (!currentMessages[currentChatId]) {
        currentMessages[currentChatId] = [];
    }
    currentMessages[currentChatId].push({ text, sender, time });
    saveChats();
}

function addMessage(text, sender, time, isError = false) {
    addMessageToUI(text, sender, time, isError);
}

function addMessageToUI(text, sender, time, isError = false) {
    const chatContainer = document.getElementById('chatContainer');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (sender === 'assistant') {
        // Parse markdown code blocks and format content
        contentDiv.innerHTML = formatMessageWithCodeBlocks(text);
    } else {
        contentDiv.textContent = text;
    }
    
    if (isError) {
        contentDiv.style.background = '#5f2c2c';
        contentDiv.style.color = '#ff6b6b';
    }
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = time;
    
    contentDiv.appendChild(timeDiv);
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function formatMessageWithCodeBlocks(text) {
    // Match code blocks with language (```language\ncode\n```) or without (```\ncode\n```)
    // Support both \n and Windows-style \r\n newlines
    const codeBlockRegex = /```(\w+)?\r?\n([\s\S]*?)```/g;
    
    let formatted = text;
    let match;
    const matches = [];
    const placeholders = [];
    
    // Find all code blocks
    while ((match = codeBlockRegex.exec(text)) !== null) {
        matches.push({
            fullMatch: match[0],
            language: match[1] || 'code',
            code: match[2]
        });
    }
    
    // Replace code blocks with placeholders first.
    // IMPORTANT: placeholder must not contain characters that our markdown formatter mutates
    // (e.g., underscores '_' are interpreted as italic/bold), otherwise we won't be able to
    // find-and-replace it back with the original code block HTML.
    matches.forEach((match, index) => {
        const placeholder = `@@@CODEBLOCK${index}@@@`;
        placeholders.push(placeholder);
        formatted = formatted.replace(match.fullMatch, placeholder);
    });
    
    // Format markdown elements
    formatted = formatMarkdown(formatted);
    
    // Replace placeholders with actual code blocks
    matches.forEach((match, index) => {
        const codeId = 'code-' + Date.now() + '-' + index;
        const escapedCode = escapeHtml(match.code);
        const codeBlockHtml = `
            <div class="code-block" data-code-id="${codeId}">
                <button class="copy-btn" onclick="copyCode('${codeId}')" title="Copy code">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"></path>
                    </svg>
                </button>
                <pre><code id="${codeId}">${escapedCode}</code></pre>
            </div>
        `;
        formatted = formatted.replace(placeholders[index], codeBlockHtml);
    });
    
    return formatted;
}

// Format markdown elements (headers, bold, lists, etc.)
function formatMarkdown(text) {
    let lines = text.split('\n');
    let formatted = [];
    let inList = false;
    let listItems = [];
    
    lines.forEach((line, index) => {
        // Headers (### ## #)
        if (line.match(/^###\s+(.+)$/)) {
            if (inList) { formatted.push(formatList(listItems)); listItems = []; inList = false; }
            const headerText = formatInlineMarkdown(line.replace(/^###\s+/, ''));
            formatted.push(`<h3 style="font-size: 1.1em; font-weight: 700; margin: 8px 0 4px 0; color: #667eea;">${headerText}</h3>`);
        }
        else if (line.match(/^##\s+(.+)$/)) {
            if (inList) { formatted.push(formatList(listItems)); listItems = []; inList = false; }
            const headerText = formatInlineMarkdown(line.replace(/^##\s+/, ''));
            formatted.push(`<h2 style="font-size: 1.3em; font-weight: 700; margin: 10px 0 4px 0; color: #667eea;">${headerText}</h2>`);
        }
        else if (line.match(/^#\s+(.+)$/)) {
            if (inList) { formatted.push(formatList(listItems)); listItems = []; inList = false; }
            const headerText = formatInlineMarkdown(line.replace(/^#\s+/, ''));
            formatted.push(`<h1 style="font-size: 1.5em; font-weight: 700; margin: 12px 0 6px 0; color: #667eea;">${headerText}</h1>`);
        }
        // Numbered lists (1. 2. 3.)
        else if (line.match(/^\d+\.\s+(.+)$/)) {
            listItems.push({ type: 'ol', content: line.replace(/^\d+\.\s+/, '') });
            inList = true;
        }
        // Bullet points (- or *)
        else if (line.match(/^[-*]\s+(.+)$/)) {
            listItems.push({ type: 'ul', content: line.replace(/^[-*]\s+/, '') });
            inList = true;
        }
        // Regular text
        else {
            if (inList && line.trim() === '') {
                formatted.push(formatList(listItems));
                listItems = [];
                inList = false;
            } else if (line.trim() !== '') {
                if (inList) { formatted.push(formatList(listItems)); listItems = []; inList = false; }
                formatted.push(line);
            } else {
                formatted.push('<br>');
            }
        }
    });
    
    // Close any remaining list
    if (inList) {
        formatted.push(formatList(listItems));
    }
    
    let result = formatted.join('<br>');
    
    // Bold text (**text** or __text__)
    result = result.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight: 700; color: #e0e0e0;">$1</strong>');
    result = result.replace(/__(.+?)__/g, '<strong style="font-weight: 700; color: #e0e0e0;">$1</strong>');
    
    // Italic text (*text* or _text_)
    result = result.replace(/\*(.+?)\*/g, '<em style="font-style: italic;">$1</em>');
    result = result.replace(/_(.+?)_/g, '<em style="font-style: italic;">$1</em>');
    
    // Inline code (`code`)
    result = result.replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 0.9em;">$1</code>');
    
    return result;
}

// Format list items (ordered or unordered)
function formatList(items) {
    if (items.length === 0) return '';
    
    const listType = items[0].type;
    const tag = listType === 'ol' ? 'ol' : 'ul';
    const listStyle = listType === 'ol' 
        ? 'list-style-type: decimal; padding-left: 24px; margin: 4px 0;' 
        : 'list-style-type: disc; padding-left: 24px; margin: 4px 0;';
    
    const listItems = items.map(item => 
        `<li style="margin: 2px 0; line-height: 1.5;">${formatInlineMarkdown(item.content)}</li>`
    ).join('');
    
    return `<${tag} style="${listStyle}">${listItems}</${tag}>`;
}

// Format inline markdown within list items
function formatInlineMarkdown(text) {
    // Bold
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight: 700;">$1</strong>');
    text = text.replace(/__(.+?)__/g, '<strong style="font-weight: 700;">$1</strong>');
    // Italic
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    text = text.replace(/_(.+?)_/g, '<em>$1</em>');
    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 0.9em;">$1</code>');
    return text;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyCode(codeId) {
    const codeElement = document.getElementById(codeId);
    if (!codeElement) return;
    
    // Get the text content which preserves newlines
    const code = codeElement.textContent;
    
    const codeBlock = document.querySelector(`[data-code-id="${codeId}"]`);
    const button = codeBlock ? codeBlock.querySelector('.copy-btn') : null;
    
    navigator.clipboard.writeText(code).then(() => {
        if (button) {
            const originalIcon = button.innerHTML;
            button.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 6L9 17l-5-5"></path>
                </svg>
            `;
            button.classList.add('copied');
            button.title = 'Copied!';
            
            setTimeout(() => {
                button.innerHTML = originalIcon;
                button.classList.remove('copied');
                button.title = 'Copy code';
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy code:', err);
    });
}

function showTypingIndicator() {
    const chatContainer = document.getElementById('chatContainer');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.id = 'typingIndicator';
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = `
        <span>Thinking</span>
        <div class="dots">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        </div>
    `;
    
    messageDiv.appendChild(typingDiv);
    chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    return messageDiv;
}

function getCurrentTime() {
    const now = new Date();
    let hours = now.getHours();
    let minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    
    return `${hours}:${minutes} ${ampm}`;
}
