package com.development.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;

import java.time.Duration;
import java.util.Map;

/**
 * Chat Controller - Acts as a gateway/proxy to the Python agent service.
 * 
 * This controller receives requests from the Angular frontend and forwards them
 * to the Python service which handles LLM orchestration, embeddings, and MCP tools.
 */
@RestController
@RequestMapping("/chat")
@CrossOrigin(origins = "*")
public class ChatController {

    @Value("${python.agent.url:http://localhost:6080}")
    private String pythonAgentUrl;

    private final RestTemplate restTemplate;

    public ChatController() {
        // Configure RestTemplate with longer timeouts (30 seconds)
        this.restTemplate = new RestTemplateBuilder()
            .setConnectTimeout(Duration.ofSeconds(1000))
            .setReadTimeout(Duration.ofSeconds(1000))
            .build();
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> chat(@RequestBody Map<String, String> body) {
        String userId = body.get("user_id");
        String chatId = body.get("chat_id");
        String message = body.get("message");
        String authorization = body.getOrDefault("authorization", "");

        // Validate inputs
        if (userId == null || userId.trim().isEmpty()) {
            return ResponseEntity.badRequest()
                .body(Map.of("error", "user_id is required"));
        }
        
        if (chatId == null || chatId.trim().isEmpty()) {
            return ResponseEntity.badRequest()
                .body(Map.of("error", "chat_id is required"));
        }
        
        if (message == null || message.trim().isEmpty()) {
            return ResponseEntity.badRequest()
                .body(Map.of("error", "message is required"));
        }

        try {
            // Forward request to Python agent service
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            
            Map<String, String> requestBody = Map.of(
                "user_id", userId,
                "chat_id", chatId,
                "message", message,
                "authorization", authorization
            );

            HttpEntity<Map<String, String>> request = new HttpEntity<>(requestBody, headers);
            
            ResponseEntity<Map> response = restTemplate.postForEntity(
                pythonAgentUrl + "/chat",
                request,
                Map.class
            );

            return ResponseEntity.ok((Map<String, Object>) response.getBody());

        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                .body(Map.of("error", "Failed to communicate with agent service: " + e.getMessage()));
        }
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        try {
            // Check Python service health
            ResponseEntity<Map> response = restTemplate.getForEntity(
                pythonAgentUrl + "/health",
                Map.class
            );
            
            return ResponseEntity.ok(Map.of(
                "status", "healthy",
                "python_service", response.getBody()
            ));
        } catch (Exception e) {
            return ResponseEntity.ok(Map.of(
                "status", "degraded",
                "message", "Python service unavailable: " + e.getMessage()
            ));
        }
    }
}
