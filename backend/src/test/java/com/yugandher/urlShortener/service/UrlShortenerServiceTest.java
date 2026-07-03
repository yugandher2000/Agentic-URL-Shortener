package com.yugandher.urlShortener.service;

import com.yugandher.urlShortener.config.AppProperties;
import com.yugandher.urlShortener.exception.UrlNotFoundException;
import com.yugandher.urlShortener.model.UrlMapping;
import com.yugandher.urlShortener.repository.UrlMappingRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.data.redis.core.types.Expiration;

import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("UrlShortenerService unit tests")
class UrlShortenerServiceTest {

    @Mock UrlMappingRepository            repository;
    @Mock StringRedisTemplate             masterRedis;
    @Mock StringRedisTemplate             replicaRedis;
    @Mock AppProperties                   props;
    @Mock ValueOperations<String, String> masterOps;
    @Mock ValueOperations<String, String> replicaOps;

    UrlShortenerService service;

    @BeforeEach
    void setUp() {
        // Manual construction — needed because @Qualifier can't be driven by Lombok here
        service = new UrlShortenerService(repository, masterRedis, replicaRedis, props);
        when(props.getBaseUrl()).thenReturn("http://localhost:8080");
        when(props.getCodeLength()).thenReturn(6);
        when(props.getCacheTtlSeconds()).thenReturn(3600L);
        when(masterRedis.opsForValue()).thenReturn(masterOps);
        when(replicaRedis.opsForValue()).thenReturn(replicaOps);
    }

    // ── shortenUrl ────────────────────────────────────────────────────────────

    @Test
    @DisplayName("shortenUrl: new URL — saves to DB and writes to master Redis")
    void shortenUrl_newUrl_savesAndCaches() {
        when(repository.findByOriginalUrl(anyString())).thenReturn(Optional.empty());
        when(repository.findByShortCode(anyString())).thenReturn(Optional.empty());
        when(repository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        String result = service.shortenUrl("https://www.example.com/very/long/path");

        assertThat(result).startsWith("http://localhost:8080/");
        assertThat(result).hasSize("http://localhost:8080/".length() + 6);
        verify(repository).save(any(UrlMapping.class));
        verify(masterOps).set(anyString(), anyString(), (Expiration) any());  // WRITE → master
        verifyNoInteractions(replicaOps);                        // replica untouched
    }

    @Test
    @DisplayName("shortenUrl: duplicate URL — returns existing, no DB insert")
    void shortenUrl_duplicateUrl_returnsExisting() {
        UrlMapping existing = UrlMapping.builder()
                .shortCode("abc123").originalUrl("https://example.com").build();
        when(repository.findByOriginalUrl("https://example.com")).thenReturn(Optional.of(existing));

        String result = service.shortenUrl("https://example.com");

        assertThat(result).isEqualTo("http://localhost:8080/abc123");
        verify(repository, never()).save(any());
    }

    // ── getOriginalUrl ────────────────────────────────────────────────────────

    @Test
    @DisplayName("getOriginalUrl: cache hit on replica — DB never called")
    void getOriginalUrl_cacheHit_replicaServes() {
        when(replicaOps.get("url:abc123")).thenReturn("https://example.com");

        String result = service.getOriginalUrl("abc123");

        assertThat(result).isEqualTo("https://example.com");
        verifyNoInteractions(repository);  // DB not touched
    }

    @Test
    @DisplayName("getOriginalUrl: replica miss — fetches DB and repopulates master")
    void getOriginalUrl_cacheMiss_fetchesDBAndRepopulates() {
        when(replicaOps.get("url:abc123")).thenReturn(null);
        UrlMapping mapping = UrlMapping.builder()
                .shortCode("abc123").originalUrl("https://example.com").build();
        when(repository.findByShortCode("abc123")).thenReturn(Optional.of(mapping));

        String result = service.getOriginalUrl("abc123");

        assertThat(result).isEqualTo("https://example.com");
        verify(masterOps).set((String) eq("url:abc123"), (String) eq("https://example.com"), (Expiration) any()); // repopulate master
    }

    @Test
    @DisplayName("getOriginalUrl: not found — throws UrlNotFoundException")
    void getOriginalUrl_notFound_throws() {
        when(replicaOps.get(anyString())).thenReturn(null);
        when(repository.findByShortCode("xxxxxx")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getOriginalUrl("xxxxxx"))
                .isInstanceOf(UrlNotFoundException.class)
                .hasMessageContaining("xxxxxx");
    }

    // ── Base62 determinism ────────────────────────────────────────────────────

    @Test
    @DisplayName("Same URL always produces the same short code")
    void shortenUrl_sameInput_deterministic() {
        when(repository.findByOriginalUrl(anyString())).thenReturn(Optional.empty());
        when(repository.findByShortCode(anyString())).thenReturn(Optional.empty());
        when(repository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        String first  = service.shortenUrl("https://deterministic-test.com");
        String second = service.shortenUrl("https://deterministic-test.com");

        // Both calls would produce the same code (second hits idempotent branch first
        // if we hadn't mocked findByOriginalUrl to return empty, but here the code
        // path is the same hash regardless — verify the code segment is identical)
        assertThat(first).isEqualTo(second);
    }
}
