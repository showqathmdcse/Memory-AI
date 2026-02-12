# 🧪 Testing Guide for NATS Streaming

This guide shows you how to test the real-time NATS streaming functionality between the Python Agent and your Spring Boot service.

## Quick Start

### 1. Test NATS Streaming (2 Terminals)

**Terminal 1 - Start NATS Subscriber:**
```bash
./test-nats-streaming.sh
```

This will subscribe to all agent messages and display them in real-time.

**Terminal 2 - Send Test Message:**
```bash
./send-test-message.sh
```

You'll see messages appear in Terminal 1 showing:
- Start event
- Response chunks
- End event

### 2. Custom Test Messages

```bash
# Custom message
./send-test-message.sh user1 chat1 "Tell me a joke"

# Another example
./send-test-message.sh user2 chat2 "What is the meaning of life?"

# Math question
./send-test-message.sh user3 chat3 "Calculate 15 * 23"
```

## What You'll See

### Terminal 1 (NATS Subscriber)
```
🎯 NATS Live Streaming Test
============================

--- Subscribing to all agent messages ---

[#1] Received on "agent.messages.user1.chat1"
{"type":"start","user_id":"user1","chat_id":"chat1","timestamp":"2025-12-20T16:52:30.123Z"}

[#2] Received on "agent.messages.user1.chat1"
{"type":"response","content":"The answer is 4","user_id":"user1","chat_id":"chat1"}

[#3] Received on "agent.messages.user1.chat1"
{"type":"end","user_id":"user1","chat_id":"chat1","timestamp":"2025-12-20T16:52:31.456Z"}
```

### Terminal 2 (Message Sender)
```
📤 Sending Test Message to Agent
=================================

User ID: test_user
Chat ID: test_chat_1703098950
Message: What is 2+2?

Sending to Python Agent at http://localhost:8000/chat...

Response:
{
  "reply": "The answer is 4"
}

✅ Message sent! Check the NATS subscriber terminal to see streaming updates.
```

## Testing Different Scenarios

### 1. Test Multiple Concurrent Messages

Open 3 terminals:

**Terminal 1:** Subscribe to NATS
```bash
./test-nats-streaming.sh
```

**Terminal 2 & 3:** Send messages simultaneously
```bash
./send-test-message.sh user1 chat1 "Question 1"
./send-test-message.sh user2 chat2 "Question 2"
```

### 2. Test Specific User Messages

Subscribe to messages from a specific user:
```bash
docker run --rm -it --network host natsio/nats-box:latest \
  nats sub 'agent.messages.user1.>'
```

### 3. Test Code Changes Stream

Subscribe to code change events:
```bash
docker run --rm -it --network host natsio/nats-box:latest \
  nats sub 'agent.code.>'
```

### 4. Monitor NATS Server

```bash
# Open NATS monitoring dashboard
open http://localhost:8222

# Or check stats via CLI
curl http://localhost:8222/varz | jq
curl http://localhost:8222/connz | jq
```

## Integration Testing

### Test with Spring Boot

Once you add NATS consumer to your Spring Boot application:

1. **Start NATS subscriber in Spring Boot logs:**
```bash
docker-compose logs -f spring-gateway
```

2. **Send a test message:**
```bash
./send-test-message.sh
```

3. **Check Spring Boot logs** - You should see:
```
INFO - Received NATS message: {"type":"start",...}
INFO - Received NATS message: {"type":"response",...}
INFO - Received NATS message: {"type":"end",...}
```

### Test with WebSocket

If you've connected your static UI to WebSocket:

1. **Open the web interface:**
```bash
open http://localhost:8081
```

2. **Open browser console** (F12)

3. **Send test message:**
```bash
./send-test-message.sh
```

4. **Check console** - You should see real-time updates

## Manual Testing with curl

### Send Chat Message
```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "manual_user",
    "chat_id": "manual_chat",
    "message": "Hello from curl!"
  }'
```

### Check Health
```bash
curl http://localhost:8000/health
curl http://localhost:8081/actuator/health  # If actuator is enabled
```

### View NATS Stream Info
```bash
docker run --rm --network host natsio/nats-box:latest \
  nats stream info AGENT_STREAM
```

### List NATS Subjects
```bash
docker run --rm --network host natsio/nats-box:latest \
  nats stream subjects AGENT_STREAM
```

## Troubleshooting

### No messages appearing in NATS subscriber

1. **Check if NATS is running:**
```bash
docker ps | grep nats
curl http://localhost:8222/varz
```

2. **Check Python Agent logs:**
```bash
docker-compose logs python-agent-service | grep NATS
```

3. **Verify NATS connection:**
```bash
docker run --rm --network host natsio/nats-box:latest \
  nats-box -s localhost:4222 server info
```

### Messages not reaching Spring Boot

1. **Check Spring Boot logs:**
```bash
docker-compose logs -f spring-gateway
```

2. **Verify NATS consumer is connected:**
```bash
curl http://localhost:8222/connz | jq
```

3. **Check network connectivity:**
```bash
docker-compose exec spring-gateway ping nats
```

### Agent not responding

1. **Check agent health:**
```bash
curl http://localhost:8000/health
```

2. **View agent logs:**
```bash
docker-compose logs -f python-agent-service
```

3. **Restart services:**
```bash
docker-compose restart python-agent-service
```

## Performance Testing

### Load Test with Multiple Messages

```bash
# Send 10 messages rapidly
for i in {1..10}; do
  ./send-test-message.sh "user$i" "chat$i" "Message $i" &
done
wait
```

### Monitor NATS Performance

```bash
# Watch NATS stats in real-time
watch -n 1 'curl -s http://localhost:8222/varz | jq ".in_msgs, .out_msgs, .in_bytes, .out_bytes"'
```

## Advanced Testing

### Test JetStream Persistence

```bash
# Create a consumer that survives restarts
docker run --rm --network host natsio/nats-box:latest \
  nats consumer add AGENT_STREAM test_consumer \
  --filter "agent.messages.>" \
  --deliver all \
  --replay instant
```

### Test Message Acknowledgment

```bash
# Subscribe with manual ack
docker run --rm -it --network host natsio/nats-box:latest \
  nats sub 'agent.messages.>' --ack
```

### Test Stream Limits

```bash
# Check stream configuration
docker run --rm --network host natsio/nats-box:latest \
  nats stream info AGENT_STREAM
```

## Useful Commands Reference

```bash
# Docker Commands
docker-compose ps                    # Check service status
docker-compose logs -f              # Follow all logs
docker-compose restart              # Restart all services
docker-compose down && docker-compose up -d  # Full restart

# NATS Commands  
nats sub 'agent.messages.>'         # Subscribe to messages
nats pub 'test.subject' 'message'   # Publish test message
nats stream ls                      # List streams
nats consumer ls AGENT_STREAM       # List consumers

# Testing Commands
./test-nats-streaming.sh            # Start NATS subscriber
./send-test-message.sh              # Send test message
curl http://localhost:8000/health   # Check agent health
curl http://localhost:8222/varz     # Check NATS stats
```

## Success Criteria

Your setup is working correctly if:

✅ NATS subscriber receives start/response/end events
✅ Python Agent responds to chat messages
✅ Messages appear in real-time (< 100ms latency)
✅ Multiple concurrent messages work correctly
✅ NATS monitoring shows active connections
✅ Spring Boot logs show NATS messages (after integration)
✅ WebSocket clients receive updates (after integration)

## Next Steps

After verifying NATS streaming works:

1. **Add NATS Consumer to Spring Boot** - See DOCKER_SETUP.md for integration code
2. **Connect Static UI via WebSocket** - Forward NATS messages to browser
3. **Update VS Code Extension** - Subscribe to NATS for real-time updates
4. **Add Error Handling** - Handle connection failures and retries
5. **Monitor in Production** - Set up alerts and logging

Happy Testing! 🚀
