# NATS Streaming Integration Guide

## Overview

Your MemoryAI application now has **real-time streaming** capabilities using NATS! The Python agent service streams responses, tool usage, and thinking processes live to the UI.

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Browser UI    │────────▶│  Spring Boot     │────────▶│  Python Agent   │
│  (JavaScript)   │◀────────│    Gateway       │◀────────│    Service      │
└─────────────────┘         └──────────────────┘         └─────────────────┘
         │                                                         │
         │                                                         │
         │                  ┌──────────────────┐                 │
         └─────────────────▶│   NATS Server    │◀────────────────┘
                            │  (WebSocket)     │
                            └──────────────────┘
```

### How It Works

1. **User sends message** → Browser sends HTTP POST to Spring Boot Gateway
2. **Gateway forwards** → Request goes to Python Agent Service  
3. **Python processes** → Agent starts thinking and using tools
4. **Real-time updates** → Python publishes events to NATS
5. **Browser receives** → JavaScript subscribes to NATS and shows live updates
6. **Final response** → Displayed in the UI

## Features Implemented

✅ **Real-Time Streaming** - See agent responses as they happen  
✅ **Tool Usage Indicators** - Watch the agent use tools live  
✅ **Thinking Messages** - See what the agent is processing  
✅ **Error Handling** - Graceful degradation if NATS is unavailable  
✅ **HTTP Fallback** - Works even without NATS (basic mode)  
✅ **Multi-Chat Support** - Each chat gets its own stream  
✅ **Auto-Reconnect** - Handles NATS disconnections

## Setup Instructions

### 1. Start NATS Server

Make sure NATS is running with WebSocket support:

```bash
# Using Docker Compose
docker-compose -f docker-compose.nats.yml up -d

# Or using Docker directly
docker run -d --name nats-server \
  -p 4222:4222 \
  -p 8222:8222 \
  nats:latest \
  -js -m 8222
```

### 2. Configure Python Service

Your Python service should publish to these NATS subjects:

```python
# Subject pattern
agent.messages.{user_id}.{chat_id}

# Example: agent.messages.test.chat_12345
```

**Message Types:**

```python
# Stream Start
{
    "type": "start",
    "user_id": "test",
    "chat_id": "chat_12345",
    "content": {}
}

# Agent Response
{
    "type": "response", 
    "user_id": "test",
    "chat_id": "chat_12345",
    "content": {
        "reply": "Agent's response text"
    }
}

# Tool Usage
{
    "type": "tool",
    "user_id": "test", 
    "chat_id": "chat_12345",
    "content": {
        "tool_name": "search_tool",
        "action": "using"
    }
}

# Thinking Updates
{
    "type": "thinking",
    "user_id": "test",
    "chat_id": "chat_12345", 
    "content": {
        "message": "Analyzing the question..."
    }
}

# Error
{
    "type": "error",
    "user_id": "test",
    "chat_id": "chat_12345",
    "content": {
        "error": "Error message"
    }
}

# Stream End
{
    "type": "end",
    "user_id": "test",
    "chat_id": "chat_12345",
    "content": {}
}
```

### 3. Start Spring Boot Gateway

```bash
# Build
mvn clean package

# Run
java -jar target/spring-boot-gateway-1.0-SNAPSHOT.jar

# Or with Maven
mvn spring-boot:run
```

### 4. Access the UI

Open your browser to:
```
http://localhost:8080
```

## Testing the Integration

### Test 1: Basic Chat

1. Open http://localhost:8080
2. Enter a User ID (e.g., "test")
3. Type a message: "Hello, how are you?"
4. Watch for:
   - ✅ Typing indicator appears
   - ✅ Real-time response streams in
   - ✅ Typing indicator disappears
   - ✅ Final message displayed

### Test 2: Tool Usage

1. Send a message that requires tools: "Search for the latest news"
2. Watch for:
   - ✅ "🔧 using tool: search_tool" message
   - ✅ Tool execution updates
   - ✅ Final result with tool data

### Test 3: Fallback Mode

1. Stop NATS: `docker stop nats-server`
2. Send a message
3. Verify:
   - ✅ Warning in console: "NATS not available - using HTTP fallback only"
   - ✅ Message still works (via HTTP)
   - ✅ Response appears (no real-time streaming)

### Test 4: Multiple Chats

1. Create a new chat (click "New chat")
2. Send messages in different chats
3. Verify:
   - ✅ Each chat gets independent streams
   - ✅ Messages only appear in correct chat
   - ✅ Switching chats works properly

## Console Logs

When NATS streaming is working, you'll see:

```javascript
// In Browser Console
Connecting to NATS...
✅ Connected to NATS successfully
📡 Subscribing to NATS subject: agent.messages.test.>
✅ Message sent - waiting for NATS stream...
📨 NATS Message: {type: "start", ...}
🚀 Stream started
📨 NATS Message: {type: "response", ...}
💬 Agent response: {...}
📨 NATS Message: {type: "end", ...}
✅ Stream ended
```

When NATS is unavailable:

```javascript
Failed to connect to NATS: Error: ...
⚠️ NATS not available - using HTTP fallback only
📡 NATS not connected - using HTTP fallback
```

## Configuration

### NATS URL

In `src/main/resources/static/script.js`:

```javascript
const NATS_CONFIG = {
    natsUrl: 'ws://localhost:4222',  // Change if NATS is on different host
    backendUrl: window.location.origin
};
```

### Python Service URL

In `src/main/resources/application.properties`:

```properties
python.agent.url=http://localhost:8000
```

## Message Flow Example

### User sends: "Hello, how are you?"

**1. Browser → Spring Boot**
```http
POST /chat HTTP/1.1
Content-Type: application/json

{
  "user_id": "test",
  "chat_id": "default", 
  "message": "Hello, how are you?"
}
```

**2. Spring Boot → Python Service**
```http
POST http://localhost:8000/chat HTTP/1.1
Content-Type: application/json

{
  "user_id": "test",
  "chat_id": "default",
  "message": "Hello, how are you?"
}
```

**3. Python Service → NATS (Real-time updates)**

```javascript
// Start
{"type": "start", "user_id": "test", "chat_id": "default"}

// Thinking
{"type": "thinking", "content": {"message": "Processing question..."}}

// Response
{"type": "response", "content": {"reply": "Hello! I'm doing well..."}}

// End
{"type": "end", "user_id": "test", "chat_id": "default"}
```

**4. NATS → Browser (WebSocket)**
```javascript
// JavaScript receives and displays each message in real-time
```

**5. Python Service → Spring Boot → Browser (HTTP Response)**
```json
{
  "reply": "Hello! I'm doing well, thank you for asking!",
  "status": "success"
}
```

## Troubleshooting

### NATS Connection Failed

**Problem:** `Failed to connect to NATS`

**Solutions:**
1. Check NATS is running: `docker ps | grep nats`
2. Verify port 4222 is accessible: `telnet localhost 4222`
3. Check NATS logs: `docker logs nats-server`
4. Ensure WebSocket is enabled in NATS config

### Messages Not Streaming

**Problem:** Response appears all at once, not streaming

**Solutions:**
1. Check browser console for NATS connection status
2. Verify Python service is publishing to correct subject
3. Check subject pattern matches: `agent.messages.{user_id}.{chat_id}`
4. Verify user_id in UI matches Python service expectations

### CORS Errors

**Problem:** CORS policy blocking requests

**Solution:** Spring Boot already has CORS enabled:
```java
@CrossOrigin(origins = "*")
```

For production, limit to specific origins:
```java
@CrossOrigin(origins = "https://yourdomain.com")
```

## Best Practices

### 1. Error Handling

Always wrap NATS operations in try-catch:

```javascript
try {
    const data = JSON.parse(new TextDecoder().decode(msg.data));
    handleNATSMessage(data);
} catch (error) {
    console.error('Error parsing NATS message:', error);
}
```

### 2. Subject Naming

Use consistent subject patterns:
- `agent.messages.{user_id}.{chat_id}` - Specific chat messages
- `agent.messages.{user_id}.>` - All user messages (wildcard)
- `agent.status.>` - System status updates

### 3. Message Size

Keep NATS messages small (<1MB recommended):
- Stream large responses in chunks
- Use references for binary data
- Compress if necessary

### 4. Connection Management

Handle connection lifecycle:
```javascript
// Reconnect on disconnect
natsConnection.closed().then(() => {
    console.log('NATS connection closed');
    // Implement reconnection logic
});
```

## Production Considerations

### Security

1. **Enable NATS Authentication**
```bash
docker run -d --name nats-server \
  -p 4222:4222 \
  nats:latest \
  -js -user admin -pass secretpassword
```

2. **Use TLS for WebSocket**
```javascript
const NATS_CONFIG = {
    natsUrl: 'wss://your-domain.com:4222',  // Use wss:// for secure
    tls: {
        ca: certificate
    }
};
```

3. **Validate Messages**
- Verify user_id matches authenticated user
- Sanitize all message content
- Rate limit NATS subscriptions

### Scalability

1. **NATS Clustering**
```bash
# Run multiple NATS servers for high availability
docker-compose -f docker-compose.nats-cluster.yml up -d
```

2. **JetStream Persistence**
```bash
# Enable message persistence
-js -store_dir /data
```

3. **Load Balancing**
- Use multiple Python service instances
- Load balance with NGINX or Spring Cloud Gateway
- NATS handles message distribution

## Summary

🎉 **Your UI now has real-time NATS streaming integrated!**

**What you get:**
- ⚡ Real-time agent responses
- 🔧 Live tool usage updates  
- 💭 Thinking process visibility
- 🔄 Automatic fallback to HTTP
- 📊 Better user experience

**Next Steps:**
1. Test with various messages
2. Monitor NATS performance
3. Add custom message types as needed
4. Deploy to production with security enabled

**Need help?** Check the logs:
- Browser Console: Developer Tools → Console
- Spring Boot: Terminal where app is running
- Python Service: Python service logs
- NATS: `docker logs nats-server`
