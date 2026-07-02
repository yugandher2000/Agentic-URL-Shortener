package com.yugandher.urlShortener.dto;

import com.yugandher.urlShortener.model.UrlMapping;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class AnalyticsResponse {

    private String shortCode;
    private String shortUrl;
    private String originalUrl;
    private Long clickCount;
    private LocalDateTime createdAt;

    public static AnalyticsResponse from(UrlMapping mapping, String baseUrl) {
        return AnalyticsResponse.builder()
                .shortCode(mapping.getShortCode())
                .shortUrl(baseUrl + "/" + mapping.getShortCode())
                .originalUrl(mapping.getOriginalUrl())
                .clickCount(mapping.getClickCount())
                .createdAt(mapping.getCreatedAt())
                .build();
    }
}
