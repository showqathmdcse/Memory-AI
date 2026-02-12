package com.development.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.config.CorsRegistry;
import org.springframework.web.reactive.config.EnableWebFlux;
import org.springframework.web.reactive.config.WebFluxConfigurer;
import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.ServerResponse;

import static org.springframework.web.reactive.function.server.RequestPredicates.GET;
import static org.springframework.web.reactive.function.server.ServerResponse.ok;

@Configuration
@EnableWebFlux
public class WebConfig implements WebFluxConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOrigins("*")
                .allowedMethods("*")
                .allowedHeaders("*")
                .maxAge(3600);
    }

    @Bean
    public RouterFunction<ServerResponse> staticResourceRouter() {
        return RouterFunctions
                .route(GET("/"), request ->
                    ok().contentType(MediaType.TEXT_HTML)
                        .bodyValue(new ClassPathResource("static/index.html")))
                .andRoute(GET("/index.html"), request ->
                    ok().contentType(MediaType.TEXT_HTML)
                        .bodyValue(new ClassPathResource("static/index.html")))
                .andRoute(GET("/style.css"), request ->
                    ok().contentType(MediaType.valueOf("text/css"))
                        .bodyValue(new ClassPathResource("static/style.css")))
                .andRoute(GET("/script.js"), request ->
                    ok().contentType(MediaType.valueOf("application/javascript"))
                        .bodyValue(new ClassPathResource("static/script.js")));
    }
}
