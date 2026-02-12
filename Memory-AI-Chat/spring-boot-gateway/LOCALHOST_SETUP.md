# Running Services on Localhost (No Docker)

This guide explains how to run the Spring Boot Gateway, Python Agent, and NATS separately on localhost.

## Prerequisites

✅ Python service running on `localhost:7000`  
✅ NATS server running on `localhost:4223`  
✅ Spring Boot Gateway configured to run on `localhost:8081`

---

## Configuration

The Spring Boot application is already configured in `src/main/resources/application.properties`:

```properties
# Server Configuration
server.port=8081

# Python Agent Service Configuration
python.agent.url=http://localhost:7000

# NATS Configuration
nats.url=nats://localhost:4223
nats.stream.name=AGENT_STREAM
```

---

## Starting the Services

### 1. Start NATS Server (Port 4223)

If not already running:

```bash
# Using Docker
docker run -p 4223:4222 -p 8222:8222 nats:latest -js

# OR using native NATS
nats-server -p 4223 -js
```

**Verify NATS is running:**
```bash
curl http://localhost:8222/varz
```

---

### 2. Start Python Agent Service (Port 7000)

Make sure your Python service is running on port 7000:

```bash
cd /path/to/python/service
python app.py  # or your startup command
```

**Verify Python service is running:**
```bash
curl http://localhost:7000/health
```

---

### 3. Start Spring Boot Gateway (Port 8081)

#### Option A: Using IntelliJ IDEA

1. Open the project in IntelliJ IDEA Ultimate
2. Navigate to `src/main/java/com/development/Main.java`
3. Click the green ▶️ play button next to the `main` method
4. The application will start on port 8081

#### Option B: Using Maven Wrapper (if available)

```bash
./mvnw spring-boot:run
```

#### Option C: Using Gradle (if you have Gradle wrapper)

```bash
./gradlew bootRun
```

#### Option D: Build and Run JAR

If you have Maven installed:

```bash
mvn clean package -DskipTests
java -jar target/spring-boot-gateway-*.jar
```

---

## Verify All Services

### Check Spring Boot Gateway Health

```bash
curl http://localhost:8081/chat/health
```

Expected response:
```json
{
  "status": "healthy",
  "python_service": { ... }
}
```

### Test the Full Stack

```bash
curl -X POST http://localhost:8081/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "chat_id": "test-chat",
    "message": "Hello, world!"
  }'
```

---

## Service URLs Summary

| Service | Port | URL |
|---------|------|-----|
| **Spring Boot Gateway** | 8081 | http://localhost:8081 |
| **Python Agent** | 7000 | http://localhost:7000 |
| **NATS Server** | 4223 | nats://localhost:4223 |
| **NATS Monitoring** | 8222 | http://localhost:8222 |

---

## Frontend Access

Once all services are running, access the web interface:

- **Main UI**: http://localhost:8081/
- **WebSocket Test**: http://localhost:8081/test-ws.html

---

## Troubleshooting

### Spring Boot won't start on 8081

Check if another process is using the port:
```bash
lsof -i :8081
# Kill the process if needed
kill -9 <PID>
```

### Cannot connect to Python service

1. Verify Python service is running: `curl http://localhost:7000/health`
2. Check firewall settings
3. Check application.properties has correct URL

### Cannot connect to NATS

1. Verify NATS is running: `curl http://localhost:8222/varz`
2. Check NATS logs for errors
3. Ensure JetStream is enabled with `-js` flag

### Maven not found

Use IntelliJ IDEA's built-in Maven:
1. Open Maven tool window (View → Tool Windows → Maven)
2. Expand Lifecycle
3. Double-click `clean` then `package`
4. Run the generated JAR from target/ directory

---

## Development Workflow

1. **Start NATS** (background service)
2. **Start Python service** on port 7000
3. **Start Spring Boot** on port 8081 via IntelliJ
4. **Access frontend** at http://localhost:8081
5. **Monitor logs** in IntelliJ console for all connections

---

## Stopping Services

1. **Spring Boot**: Click the red ⏹️ stop button in IntelliJ, or Ctrl+C in terminal
2. **Python Service**: Ctrl+C in its terminal
3. **NATS**: `docker stop <container>` or Ctrl+C if running natively

---

## Next Steps

- Test the chat functionality via the web UI
- Monitor NATS messages using the NATS CLI tools
- Check logs for any connection issues
- Use SSE endpoint for real-time updates: http://localhost:8081/sse/stream

---

## Notes

- No Docker networking needed - all services communicate via localhost
- Spring Boot will auto-reconnect to NATS if connection drops
- Python service health is checked by Spring Boot gateway
- WebSocket and SSE endpoints are available for real-time communication
