package com.development.tools;

import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;

@Component
public class ToolRegistry {

    private Map<String, Function<Map<String,Object>, Object>> tools = new HashMap<>();

    public void register(String name, Function<Map<String,Object>, Object> fn) {
        tools.put(name, fn);
    }

    public Optional<Object> call(String name, Map<String,Object> args) {
        if (!tools.containsKey(name)) return Optional.empty();
        return Optional.ofNullable(tools.get(name).apply(args));
    }
}
