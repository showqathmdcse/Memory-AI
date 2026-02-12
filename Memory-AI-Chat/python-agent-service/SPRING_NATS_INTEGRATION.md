# Spring Boot + Python + NATS Streaming Integration Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        NATS JetStream                            │
│                      (localhost:4222)                            │
│                                                                   │
│     Subjects:                                                    │
│     - agent.messages.{user_id}.{chat_id}                        │
│     - agent.code.{user_id}.{chat_id}                            │
│                                                                   │
└───────────┬────────────────────────┬──────────────────┬─────────┘
            │                        │                  │
            ▼                        ▼                  ▼
    ┌───────────────┐       ┌──────────────┐   ┌─────────────┐
    │  Spring Boot  │       │   Python     │   │  Static UI  │
    │   Service     │       │   Agent      │   │  (Browser)  │
    │  Port 8081    │       │  Port 8000   │   │             │
    │               │       │              │   │  WebSocket  │
    │  - REST API   │◄─────►│  - Chat API  │   │  to NATS    │
    │  - MCP Server │       │  - Tools     │   │             │
    └───────────────┘       └──────────────┘   └─────────────┘
            │                        │
            │                        │
            ▼                        ▼
    VS Code Extension         VS Code Extension
    (Connects to both)        (Connects to both)
```

## Current Setup

### ✅ Python Agent Service (Port 8000)
- **Status**: Running with NATS enabled
- **NATS URL**: `nats://localhost:4222`
- **Features**:
  - Chat API endpoint
  - Real-time streaming to NATS
  - Agent thinking logs
  - MCP client (connects to Spring on 8081)

### ⚙️ Spring Boot Service (Port 8081)
- **Status**: Needs NATS integration
- **Role**: MCP Server provider
- **Needs**:
  - NATS client dependency
  - Streaming configuration
  - Event publishers

## Spring Boot NATS Integration

### Step 1: Add Dependencies

Add to `pom.xml`:

```xml
<dependencies>
    <!-- NATS Java Client -->
    <dependency>
        <groupId>io.nats</groupId>
        <artifactId>jnats</artifactId>
        <version>2.17.0</version>
    </dependency>
    
    <!-- Spring Boot Starter -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter</artifactId>
    </dependency>
</dependencies>
```

### Step 2: NATS Configuration

Create `src/main/resources/application.yml`:

```yaml
spring:
  application:
    name: spring-mcp-service

server:
  port: 8081

# NATS Configuration
nats:
  url: nats://localhost:4222
  stream:
    name: AGENT_STREAM
    subjects:
      messages: agent.messages
      code: agent.code
  max-reconnect: 60
  connection-timeout: 2000
```

### Step 3: NATS Configuration Class

Create `src/main/java/com/example/config/NatsConfig.java`:

```java
package com.example.config;

import io.nats.client.Connection;
import io.nats.client.JetStream;
import io.nats.client.JetStreamManagement;
import io.nats.client.Nats;
import io.nats.client.api.StreamConfiguration;
import io.nats.client.api.StreamInfo;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.IOException;
import java.time.Duration;

@Configuration
public class NatsConfig {
    
    private static final Logger log = LoggerFactory.getLogger(NatsConfig.class);
    
    @Value("${nats.url:nats://localhost:4222}")
    private String natsUrl;
    
    @Value("${nats.stream.name:AGENT_STREAM}")
    private String streamName;
    
    @Bean
    public Connection natsConnection() throws IOException, InterruptedException {
        log.info("Connecting to NATS at: {}", natsUrl);
        Connection nc = Nats.connect(natsUrl);
        log.info("✅ Connected to NATS successfully");
        return nc;
    }
    
    @Bean
    public JetStream jetStream(Connection natsConnection) throws IOException, InterruptedException {
        JetStream js = natsConnection.jetStream();
        
        // Ensure stream exists
        JetStreamManagement jsm = natsConnection.jetStreamManagement();
        try {
            StreamInfo streamInfo = jsm.getStreamInfo(streamName);
            log.info("✅ JetStream '{}' already exists", streamName);
        } catch (Exception e) {
            // Create stream if it doesn't exist
            StreamConfiguration streamConfig = StreamConfiguration.builder()
                .name(streamName)
                .subjects("agent.messages.*", "agent.code.*")
                .maxAge(Duration.ofHours(24))
                .maxMessages(10000)
                .maxBytes(10 * 1024 * 1024) // 10MB
                .build();
            
            jsm.addStream(streamConfig);
            log.info("✅ Created JetStream: {}", streamName);
        }
        
        return js;
    }
}
```

### Step 4: NATS Publisher Service

Create `src/main/java/com/example/service/NatsPublisherService.java`:

```java
package com.example.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.nats.client.JetStream;
import io.nats.client.api.PublishAck;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class NatsPublisherService {
    
    private static final Logger log = LoggerFactory.getLogger(NatsPublisherService.class);
    
    private final JetStream jetStream;
    private final ObjectMapper objectMapper;
    
    public NatsPublisherService(JetStream jetStream, ObjectMapper objectMapper) {
        this.jetStream = jetStream;
        this.objectMapper = objectMapper;
    }
    
    /**
     * Stream agent message to NATS
     */
    public void streamAgentMessage(
            String userId, 
            String chatId, 
            String messageType, 
            Object content
    ) {
        try {
            String subject = String.format("agent.messages.%s.%s", userId, chatId);
            
            Map<String, Object> message = new HashMap<>();
            message.put("type", messageType);
            message.put("user_id", userId);
            message.put("chat_id", chatId);
            message.put("content", content);
            message.put("timestamp", System.currentTimeMillis() / 1000.0);
            
            String json = objectMapper.writeValueAsString(message);
            PublishAck ack = jetStream.publish(subject, json.getBytes());
            
            log.debug("📨 Published to NATS: {} - seq: {}", messageType, ack.getSeqno());
            
        } catch (Exception e) {
            log.error("❌ Failed to publish to NATS: {}", e.getMessage());
        }
    }
    
    /**
     * Stream code changes to NATS
     */
    public void streamCodeChange(
            String userId,
            String chatId,
            String filePath,
            String content,
            String operation
    ) {
        try {
            String subject = String.format("agent.code.%s.%s", userId, chatId);
            
            Map<String, Object> message = new HashMap<>();
            message.put("type", "file_change");
            message.put("user_id", userId);
            message.put("chat_id", chatId);
            message.put("file_path", filePath);
            message.put("content", content);
            message.put("operation", operation);
            message.put("timestamp", System.currentTimeMillis() / 1000.0);
            
            String json = objectMapper.writeValueAsString(message);
            jetStream.publish(subject, json.getBytes());
            
            log.debug("📨 Published code change to NATS: {}", filePath);
            
        } catch (Exception e) {
            log.error("❌ Failed to publish code change: {}", e.getMessage());
        }
    }
    
    /**
     * Stream tool execution details
     */
    public void streamToolExecution(
            String userId,
            String chatId,
            String toolName,
