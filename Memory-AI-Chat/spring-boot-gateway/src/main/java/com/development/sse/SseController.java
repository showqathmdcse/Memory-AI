package com.development.sse;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@RestController
public class SseController {

    private final Map<String, Sinks.Many<ServerSentEvent<String>>> emitters = new ConcurrentHashMap<>();

    @GetMapping(value = "/sse/agent", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<String>> streamEvents(@RequestParam(required = false) String chatId) {
        String sessionId = chatId != null ? chatId : "default_" + System.currentTimeMillis();
        
        Sinks.Many<ServerSentEvent<String>> sink = Sinks.many().multicast().onBackpressureBuffer();
        emitters.put(sessionId, sink);
        
        log.info("SSE connection established: {} (Total: {})", sessionId, emitters.size());

        // Send initial connection event
        sink.tryEmitNext(ServerSentEvent.<String>builder()
            .event("connected")
            .data("{\"type\":\"connected\",\"sessionId\":\"" + sessionId + "\"}")
            .build());

        return sink.asFlux()
            .doOnCancel(() -> {
                emitters.remove(sessionId);
                log.info("SSE connection cancelled: {} (Total: {})", sessionId, emitters.size());
            })
            .doOnComplete(() -> {
                emitters.remove(sessionId);
                log.info("SSE connection completed: {} (Total: {})", sessionId, emitters.size());
            })
            .doOnError(error -> {
                emitters.remove(sessionId);
                log.error("SSE connection error: {} - {}", sessionId, error.getMessage());
            });
    }

    /**
     * Broadcast a message to all connected SSE clients
     */
    public void broadcast(String message) {
        log.debug("Broadcasting message to {} SSE clients", emitters.size());
        
        ServerSentEvent<String> event = ServerSentEvent.<String>builder()
            .event("message")
            .data(message)
            .build();
        
        emitters.forEach((sessionId, sink) -> {
            try {
                sink.tryEmitNext(event);
            } catch (Exception e) {
                log.error("Error broadcasting to SSE client {}: {}", sessionId, e.getMessage());
                emitters.remove(sessionId);
            }
        });
    }

    /**
     * Send a message to a specific SSE client
     */
    public void sendToSession(String sessionId, String message) {
        Sinks.Many<ServerSentEvent<String>> sink = emitters.get(sessionId);
        if (sink != null) {
            try {
                ServerSentEvent<String> event = ServerSentEvent.<String>builder()
                    .event("message")
                    .data(message)
                    .build();
                sink.tryEmitNext(event);
            } catch (Exception e) {
                log.error("Error sending to SSE session {}: {}", sessionId, e.getMessage());
                emitters.remove(sessionId);
            }
        }
    }

    /**
     * Get the number of active SSE connections
     */
    public int getActiveConnectionCount() {
        return emitters.size();
    }
}
