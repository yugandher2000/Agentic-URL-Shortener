package com.yugandher.urlShortener.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Getter
@Setter
@Component
@ConfigurationProperties(prefix = "url")
public class AppProperties {
    private String baseUrl = "http://localhost:8080";
    private int codeLength = 6;
    private long cacheTtlSeconds = 3600;
}
