package com.development.service;

import com.development.sse.SseController;
import io.nats.client.*;
import io.nats.client.api.StorageType;
import io.nats.client.api.StreamConfiguration;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

@Slf4j
@Service
public class NatsConsumerService {

    @Value("${nats.url:nats://localhost:4222}")
    private String natsUrl;

    @Value("${nats.stream.name:AGENT_STREAM}")
    private String streamName;

    private final SseController sseController;
    private Connection natsConnection;
    private JetStream jetStream;
    private JetStreamManagement jsm;

    public NatsConsumerService(SseController sseController) {
        this.sseController = sseController;
    }

    @PostConstruct
    public void initialize() {
        try {
            connectToNats();
            subscribeToAgentMessages();
            log.info("✅ NATS consumer service initialized successfully");
        } catch (Exception e) {
            log.error("❌ Failed to initialize NATS consumer service: {}", e.getMessage(), e);
        }
    }

    private void connectToNats() throws IOException, InterruptedException {
        log.info("Connecting to NATS at {}", natsUrl);
        
        Options options = new Options.Builder()
                .server(natsUrl)
                .connectionTimeout(Duration.ofSeconds(10))
                .pingInterval(Duration.ofSeconds(120))
                .reconnectWait(Duration.ofSeconds(2))
                .maxReconnects(-1) // Infinite reconnects
                .errorListener(new ErrorListener() {
                    @Override
                    public void errorOccurred(Connection conn, String error) {
                        log.error("NATS error: {}", error);
                    }

                    @Override
                    public void exceptionOccurred(Connection conn, Exception exp) {
                        log.error("NATS exception: {}", exp.getMessage(), exp);
                    }

                    @Override
                    public void slowConsumerDetected(Connection conn, Consumer consumer) {
                        log.warn("Slow consumer detected: {}", consumer);
                    }
                })
                .connectionListener((conn, type) -> {
                    log.info("NATS connection event: {}", type);
                })
                .build();

        natsConnection = Nats.connect(options);
        jetStream = natsConnection.jetStream();
        jsm = natsConnection.jetStreamManagement();
        
        log.info("✅ Connected to NATS successfully");
    }

    private void subscribeToAgentMessages() {
        if (jetStream == null) {
            log.error("JetStream not initialized, cannot subscribe");
            return;
        }

        try {
            // Ensure the stream exists, create if it doesn't
            ensureStreamExists();
            
            // Subscribe to all agent messages
            String subject = "agent.messages.>";
            
            PushSubscribeOptions subscribeOptions = PushSubscribeOptions.builder()
                    .stream(streamName)
                    .build();

            log.info("📡 Subscribing to NATS subject: {}", subject);
            
            Dispatcher dispatcher = natsConnection.createDispatcher();
            
            jetStream.subscribe(subject, dispatcher, msg -> {
                try {
                    String data = new String(msg.getData(), StandardCharsets.UTF_8);
                    log.debug("📨 Received NATS message on {}: {}", msg.getSubject(), data);
                    
                    // Forward to all SSE clients
                    sseController.broadcast(data);
                    
                    // Acknowledge the message
                    msg.ack();
                    
                } catch (Exception e) {
                    log.error("Error processing NATS message: {}", e.getMessage(), e);
                }
            }, false, subscribeOptions);
            
            log.info("✅ Successfully subscribed to {}", subject);
            
            // Also subscribe to code changes
            String codeSubject = "agent.code.>";
            jetStream.subscribe(codeSubject, dispatcher, msg -> {
                try {
                    String data = new String(msg.getData(), StandardCharsets.UTF_8);
                    log.debug("📨 Received code change on {}: {}", msg.getSubject(), data);
                    
                    // Forward to all SSE clients
                    sseController.broadcast(data);
                    
                    // Acknowledge the message
                    msg.ack();
                    
                } catch (Exception e) {
                    log.error("Error processing code change: {}", e.getMessage(), e);
                }
            }, false, subscribeOptions);
            
            log.info("✅ Successfully subscribed to {}", codeSubject);
            
        } catch (IOException | JetStreamApiException e) {
            log.error("Failed to subscribe to NATS: {}", e.getMessage(), e);
        }
    }

    @PreDestroy
    public void cleanup() {
        log.info("Shutting down NATS consumer service...");
        
        if (natsConnection != null && !natsConnection.getStatus().equals(Connection.Status.CLOSED)) {
            try {
                natsConnection.close();
                log.info("✅ NATS connection closed successfully");
            } catch (InterruptedException e) {
                log.error("Error closing NATS connection: {}", e.getMessage(), e);
                Thread.currentThread().interrupt();
            }
        }
    }

    private void ensureStreamExists() {
        try {
            // Try to get stream info
            jsm.getStreamInfo(streamName);
            log.info("✅ Stream {} already exists", streamName);
        } catch (JetStreamApiException e) {
            if (e.getErrorCode() == 10059) { // Stream not found
                log.info("📦 Creating NATS stream: {}", streamName);
                try {
                    StreamConfiguration streamConfig = StreamConfiguration.builder()
                            .name(streamName)
                            .subjects("agent.>")
                            .storageType(StorageType.Memory)
                            .build();
                    
                    jsm.addStream(streamConfig);
                    log.info("✅ Successfully created stream: {}", streamName);
                } catch (IOException | JetStreamApiException ex) {
                    log.error("Failed to create stream: {}", ex.getMessage(), ex);
                    throw new RuntimeException("Failed to create NATS stream", ex);
                }
            } else {
                log.error("Error checking stream: {}", e.getMessage(), e);
                throw new RuntimeException("Failed to check NATS stream", e);
            }
        } catch (IOException e) {
            log.error("IO error checking stream: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to check NATS stream", e);
        }
    }

    /**
     * Check if NATS is connected
     */
    public boolean isConnected() {
        return natsConnection != null && 
               natsConnection.getStatus().equals(Connection.Status.CONNECTED);
    }

    /**
     * Get connection status
     */
    public Connection.Status getStatus() {
        return natsConnection != null ? natsConnection.getStatus() : Connection.Status.CLOSED;
    }
}
