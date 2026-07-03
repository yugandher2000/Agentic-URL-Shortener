package com.yugandher.urlShortener.controller;

import com.yugandher.urlShortener.config.AppProperties;
import com.yugandher.urlShortener.dto.AnalyticsResponse;
import com.yugandher.urlShortener.dto.ShortenRequest;
import com.yugandher.urlShortener.dto.ShortenResponse;
import com.yugandher.urlShortener.model.UrlMapping;
import com.yugandher.urlShortener.service.UrlShortenerService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;

@RestController
@RequiredArgsConstructor
@CrossOrigin(origins = "*")   // tighten to specific origin in production
public class UrlShortenerController {

    private final UrlShortenerService service;
    private final AppProperties       props;

    /**
     * POST /api/shorten
     * Body: { "longUrl": "https://..." }
     * Returns: { "shortUrl": "http://localhost:8080/aB3xZ9" }
     */
    @PostMapping("/api/shorten")
    public ResponseEntity<ShortenResponse> shorten(@Valid @RequestBody ShortenRequest request) {
        String shortUrl = service.shortenUrl(request.getLongUrl());
        return ResponseEntity.ok(new ShortenResponse(shortUrl));
    }

    /**
     * GET /{shortCode}
     * Redirects (302) to the original URL and records the click.
     */
    @GetMapping("/{shortCode}")
    public ResponseEntity<Void> redirect(@PathVariable String shortCode) {
        String originalUrl = service.getOriginalUrl(shortCode);
        service.recordClick(shortCode);
        return ResponseEntity.status(302)
                .location(URI.create(originalUrl))
                .build();
    }

    /**
     * GET /api/analytics/{shortCode}
     * Returns click count, creation time, and both URL forms.
     */
    @GetMapping("/api/analytics/{shortCode}")
    public ResponseEntity<AnalyticsResponse> analytics(@PathVariable String shortCode) {
        UrlMapping mapping = service.getAnalytics(shortCode);
        return ResponseEntity.ok(AnalyticsResponse.from(mapping, props.getBaseUrl()));
    }
}
