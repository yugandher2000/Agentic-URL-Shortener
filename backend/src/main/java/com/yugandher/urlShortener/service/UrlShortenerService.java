package com.yugandher.urlShortener.service;

import com.yugandher.urlShortener.config.AppProperties;
import com.yugandher.urlShortener.exception.UrlNotFoundException;
import com.yugandher.urlShortener.model.UrlMapping;
import com.yugandher.urlShortener.repository.UrlMappingRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.Optional;

/**
 * Core business logic for the URL shortener.
 *
 * Redis architecture:
 *   WRITE (cache population) → masterRedisTemplate (Redis Master)
 *   READ  (cache lookup)     → replicaRedisTemplate (Redis Replica)
 *
 * Short code algorithm:
 *   1. SHA-256 hash of the original URL
 *   2. Take 8 bytes → interpret as unsigned long
 *   3. Base62-encode to exactly 6 chars
 *   4. On collision: append an attempt counter and repeat (bounded)
 */
@Service
@Slf4j
public class UrlShortenerService {

    private static final String BASE62       = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
    private static final String REDIS_PREFIX = "url:";

    private final UrlMappingRepository repository;
    private final StringRedisTemplate   masterRedis;   // WRITES
    private final StringRedisTemplate   replicaRedis;  // READS
    private final AppProperties         props;

    public UrlShortenerService(
            UrlMappingRepository repository,
            @Qualifier("masterRedisTemplate")  StringRedisTemplate masterRedis,
            @Qualifier("replicaRedisTemplate") StringRedisTemplate replicaRedis,
            AppProperties props) {
        this.repository   = repository;
        this.masterRedis  = masterRedis;
        this.replicaRedis = replicaRedis;
        this.props        = props;
    }

    // ── Shorten ───────────────────────────────────────────────────────────────

    @Transactional
    public String shortenUrl(String originalUrl) {
        // Idempotent: return existing short URL if already known
        Optional<UrlMapping> existing = repository.findByOriginalUrl(originalUrl);
        if (existing.isPresent()) {
            writeToMaster(existing.get().getShortCode(), originalUrl);
            return buildShortUrl(existing.get().getShortCode());
        }

        // Generate code with bounded collision resolution
        String shortCode = generateCode(originalUrl, 0);
        int attempt = 1;
        while (repository.findByShortCode(shortCode).isPresent() && attempt <= 10) {
            shortCode = generateCode(originalUrl, attempt++);
        }

        UrlMapping mapping = UrlMapping.builder()
                .shortCode(shortCode)
                .originalUrl(originalUrl)
                .build();
        repository.save(mapping);

        // WRITE → master node
        writeToMaster(shortCode, originalUrl);

        log.info("Shortened: {} → {}", originalUrl, shortCode);
        return buildShortUrl(shortCode);
    }

    // ── Resolve ───────────────────────────────────────────────────────────────

    @Transactional(readOnly = true)
    public String getOriginalUrl(String shortCode) {
        // READ → replica node first
        String cached = replicaRedis.opsForValue().get(REDIS_PREFIX + shortCode);
        if (cached != null) {
            log.debug("Cache hit (replica): {}", shortCode);
            return cached;
        }

        // Cache miss → fallback to DB
        UrlMapping mapping = repository.findByShortCode(shortCode)
                .orElseThrow(() -> new UrlNotFoundException(shortCode));

        // Repopulate master (replica will replicate)
        writeToMaster(shortCode, mapping.getOriginalUrl());
        return mapping.getOriginalUrl();
    }

    // ── Analytics ─────────────────────────────────────────────────────────────

    @Transactional
    public void recordClick(String shortCode) {
        repository.incrementClickCount(shortCode);
    }

    @Transactional(readOnly = true)
    public UrlMapping getAnalytics(String shortCode) {
        return repository.findByShortCode(shortCode)
                .orElseThrow(() -> new UrlNotFoundException(shortCode));
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void writeToMaster(String shortCode, String originalUrl) {
        masterRedis.opsForValue().set(
                REDIS_PREFIX + shortCode,
                originalUrl,
                Duration.ofSeconds(props.getCacheTtlSeconds())
        );
    }

    public String buildShortUrl(String shortCode) {
        return props.getBaseUrl() + "/" + shortCode;
    }

    private String generateCode(String originalUrl, int attempt) {
        try {
            String input = attempt == 0 ? originalUrl : originalUrl + "_" + attempt;
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));

            long value = 0;
            for (int i = 0; i < 8; i++) {
                value = (value << 8) | (hash[i] & 0xFFL);
            }
            // Mask sign bit → always non-negative, no overflow risk
            value = value & Long.MAX_VALUE;

            return toBase62(value, props.getCodeLength());
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    private String toBase62(long value, int length) {
        char[] buf = new char[length];
        for (int i = length - 1; i >= 0; i--) {
            buf[i] = BASE62.charAt((int) Math.floorMod(value, 62L));
            value = Math.floorDiv(value, 62L);
        }
        return new String(buf);
    }
}
