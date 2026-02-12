package com.development.websocket;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.socket.WebSocketHandler;
import org.springframework.web.reactive.socket.WebSocketSession;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.core.publisher.Sinks;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Component
public class AgentWebSocketHandler implements WebSocketHandler {

    private final Map<String, Sinks.Many<String>> sessions = new ConcurrentHashMap<>();

    @Override
    public Mono<Void> handle(WebSocketSession session) {
        String sessionId = session.getId();
        Sinks.Many<String> sink = Sinks.many().multicast().onBackpressureBuffer();
        
        sessions.put(sessionId, sink);
        log.info("WebSocket connection established: {}", sessionId);
        log.info("Total active sessions: {}", sessions.size());

        // Send messages from sink to client
        Mono<Void> output = session.send(
            sink.asFlux()
                .map(session::textMessage)
                .doOnError(error -> log.error("Error sending message: {}", error.getMessage()))
        );

        // Receive messages from client (optional, for future use)
        Mono<Void> input = session.receive()
            .doOnNext(message -> {
                log.debug("Received message from client {}: {}", sessionId, message.getPayloadAsText());
            })
            .then();

        // Clean up on connection close
        return Mono.zip(input, output)
            .doFinally(signalType -> {
                sessions.remove(sessionId);
                log.info("WebSocket connection closed: {} - Signal: {}", sessionId, signalType);
                log.info("Total active sessions: {}", sessions.size());
            })
            .then();
    }

    /**
     * Broadcast a message to all connected WebSocket clients
     */
    public void broadcast(String message) {
        log.debug("Broadcasting message to {} sessions: {}", sessions.size(), message);
        
        sessions.values().forEach(sink -> {
            try {
                sink.tryEmitNext(message);
            } catch (Exception e) {
                log.error("Error broadcasting message: {}", e.getMessage());
            }
        });
    }

    /**
     * Send a message to a specific WebSocket client
     */
    public void sendToSession(String sessionId, String message) {
        Sinks.Many<String> sink = sessions.get(sessionId);
        if (sink != null) {
            try {
                sink.tryEmitNext(message);
            } catch (Exception e) {
                log.error("Error sending message to session {}: {}", sessionId, e.getMessage());
            }
        }
    }

    /**
     * Get the number of active sessions
     */
    public int getActiveSessionCount() {
        return sessions.size();
    }
}
