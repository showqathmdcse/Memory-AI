# Enable Real-Time Token Streaming

## Current Behavior

The Python agent currently:
1. Calls OpenAI with `stream=False`
2. Waits for the **complete response**
3. Sends one NATS message with the full response
4. UI shows "Thinking..." then displays complete response

**Evidence from logs:**
```python
'stream': False  # ← This prevents token-by-token streaming
```

## Desired Behavior

For real-time streaming (like ChatGPT):
1. Call OpenAI with `stream=True`
2. Process each **token/chunk** as it arrives
3. Send each chunk to NATS immediately
4. UI displays tokens as they arrive

## Required Changes in Python Agent

### 1. Enable Streaming in OpenAI Call

**Current code (approximate):**
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    stream=False,  # ← Change this
    temperature=0.7
)
```

**Updated code:**
```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    stream=True,   # ← Enable streaming
    temperature=0.7
)
```

### 2. Process Streaming Response

**Current code sends complete response:**
```python
# Wait for complete response
result = response.choices[0].message.content

# Send to NATS
await nats_producer.publish_message(
    user_id, chat_id, "response", {"reply": result}
)
```

**Updated code sends tokens:**
```python
# Stream tokens as they arrive
for chunk in response:
    if chunk.choices[0].delta.content:
        token = chunk.choices[0].delta.content
        
        # Send each token immediately to NATS
        await nats_producer.publish_message(
            user_id, chat_id, "token", {"content": token}
        )

# Send completion message
await nats_producer.publish_message(
    user_id, chat_id, "end", {"status": "completed"}
)
```

### 3. Update NATS Message Types

**Current message types:**
- `start` - Request received
- `response` - **Complete response** (sent once)
- `end` - Completion

**New message types:**
- `start` - Request received
- `token` - **Individual token** (sent multiple times as tokens arrive)
- `end` - Completion

## Frontend Already Supports This!

The Spring Boot gateway and frontend are already configured to handle streaming:

**WebSocket Handler** broadcasts all messages:
```java
// Already working - broadcasts each message
websocketSessions.forEach(session -> {
    session.send(Mono.just(textMessage));
});
```

**Frontend** needs minor update to handle `token` type:
```javascript
case 'token':
    handleStreamingToken(data);
    break;
```

## Implementation Steps

### Step 1: Update Python Agent

File: `agent_service.py` or similar

```python
async def chat_with_streaming(user_id: str, chat_id: str, message: str):
    # Send start message
    await nats_producer.publish_message(
        user_id, chat_id, "start", {"message": message}
    )
    
    # Call OpenAI with streaming
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history,
        stream=True,  # Enable streaming
        temperature=0.7
    )
    
    # Stream tokens
    full_response = ""
    async for chunk in response:
        if chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_response += token
            
            # Send token immediately
            await nats_producer.publish_message(
                user_id, chat_id, "token", {"content": token}
            )
    
    # Save complete response to memory
    await memory.save_message(user_id, chat_id, full_response)
    
    # Send completion
    await nats_producer.publish_message(
        user_id, chat_id, "end", {"status": "completed"}
    )
```

### Step 2: Update Frontend (script.js)

Add handler for `token` messages:

```javascript
function handleStreamMessage(data) {
    switch (data.type) {
        case 'start':
            handleStreamStart(data);
            break;
            
        case 'token':  // NEW: Handle streaming tokens
            handleStreamingToken(data);
            break;
            
        case 'response':  // Keep for backward compatibility
            handleStreamResponse(data);
            break;
            
        case 'end':
            handleStreamEnd(data);
            break;
    }
}

// NEW: Handle individual tokens
function handleStreamingToken(data) {
    const token = data.content.content || data.content;
    
    // Append to streaming message
    if (!currentStreamingMessage) {
        // Create new streaming message
        const assistantTime = getCurrentTime();
        currentStreamingMessage = createStreamingMessage('assistant', assistantTime);
    }
    
    // Append token to message
    appendTokenToMessage(currentStreamingMessage, token);
}

function createStreamingMessage(sender, time) {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.id = 'streaming-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.id = 'streaming-content';
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = time;
    
    contentDiv.appendChild(timeDiv);
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);
    
    return messageDiv;
}

function appendTokenToMessage(messageDiv, token) {
    const contentDiv = messageDiv.querySelector('#streaming-content');
    if (contentDiv) {
        const currentText = contentDiv.textContent;
        contentDiv.textContent = currentText + token;
        
        // Auto-scroll
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}
```

### Step 3: Update handleStreamEnd

```javascript
function handleStreamEnd(data) {
    console.log('✅ Stream ended');
    
    // Remove typing indicator
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
    
    // Finalize streaming message
    if (currentStreamingMessage) {
        const content = currentStreamingMessage.querySelector('#streaming-content').textContent;
        storeMessage(content, 'assistant', getCurrentTime());
        currentStreamingMessage.id = ''; // Remove streaming ID
        currentStreamingMessage = null;
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
```

## Testing

After implementing changes:

1. Send a message from the UI
2. You should see tokens appearing one by one (like ChatGPT)
3. NATS will show multiple `token` messages instead of one `response`

## Summary

**Problem:** Python agent uses `stream=False`
**Solution:** Change to `stream=True` and send tokens individually
**Result:** Real-time token-by-token display in UI

The Spring Boot gateway and NATS infrastructure are already ready for streaming - only the Python agent needs to be modified to enable OpenAI streaming and send tokens as they arrive.
