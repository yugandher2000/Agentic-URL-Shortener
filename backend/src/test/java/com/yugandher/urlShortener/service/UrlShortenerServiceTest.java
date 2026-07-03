
import com.yugandher.urlShortener.model.UrlMapping;
import com.yugandher.urlShortener.repository.UrlMappingRepository;
import com.yugandher.urlShortener.service.UrlShortenerService;
import com.yugandher.urlShortener.util.AppProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class UrlShortenerServiceTest {

    @Mock
    private UrlMappingRepository urlMappingRepository;

    @Mock
    private RedisTemplate<String, String> masterRedisTemplate;

    @Mock
    private RedisTemplate<String, String> replicaRedisTemplate;

    @Mock
    private AppProperties appProperties;

    @InjectMocks
    private UrlShortenerService urlShortenerService;

    @Test
    void shortenUrl_returnsShortUrl() {
        // Given
        String originalUrl = "https://example.com";
        String shortCode = "abc123";
        UrlMapping urlMapping = UrlMapping.builder()
                .id(1L)
                .shortCode(shortCode)
                .originalUrl(originalUrl)
                .createdAt(LocalDateTime.now())
                .clickCount(0L)
                .build();

        when(urlMappingRepository.findByOriginalUrl(originalUrl)).thenReturn(Optional.empty());
        when(urlMappingRepository.save(any(UrlMapping.class))).thenReturn(urlMapping);

        // When
        String shortUrl = urlShortenerService.shortenUrl(originalUrl);

        // Then
        assertEquals("https://example.com/" + shortCode, shortUrl);
        verify(urlMappingRepository, times(1)).save(any(UrlMapping.class));
    }

    @Test
    void shortenUrl_idempotent() {
        // Given
        String originalUrl = "https://example.com";
        String shortCode = "abc123";
        UrlMapping urlMapping = UrlMapping.builder()
                .id(1L)
                .shortCode(shortCode)
                .originalUrl(originalUrl)
                .createdAt(LocalDateTime.now())
                .clickCount(0L)
                .build();

        when(urlMappingRepository.findByOriginalUrl(originalUrl)).thenReturn(Optional.of(urlMapping));

        // When
        String shortUrl = urlShortenerService.shortenUrl(originalUrl);

        // Then
        assertEquals("https://example.com/" + shortCode, shortUrl);
        verify(urlMappingRepository, never()).save(any(UrlMapping.class));
    }

    @Test
    void getOriginalUrl_cacheHit() {
        // Given
        String shortCode = "abc123";
        String originalUrl = "https://example.com";
        ValueOperations<String, String> valueOperations = mock(ValueOperations.class);
        when(masterRedisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(shortCode)).thenReturn(originalUrl);

        // When
        String result = urlShortenerService.getOriginalUrl(shortCode);

        // Then
        assertEquals(originalUrl, result);
        verify(urlMappingRepository, never()).findByShortCode(shortCode);
    }

    @Test
    void getOriginalUrl_cacheMiss() {
        // Given
        String shortCode = "abc123";
        String originalUrl = "https://example.com";
        UrlMapping urlMapping = UrlMapping.builder()
                .id(1L)
                .shortCode(shortCode)
                .originalUrl(originalUrl)
                .createdAt(LocalDateTime.now())
                .clickCount(0L)
                .build();

        ValueOperations<String, String> valueOperations = mock(ValueOperations.class);
        when(masterRedisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(shortCode)).thenReturn(null);
        when(urlMappingRepository.findByShortCode(shortCode)).thenReturn(Optional.of(urlMapping));

        // When
        String result = urlShortenerService.getOriginalUrl(shortCode);

        // Then
        assertEquals(originalUrl, result);
        verify(urlMappingRepository, times(1)).findByShortCode(shortCode);
    }

    @Test
    void recordClick_callsRepo() {
        // Given
        String shortCode = "abc123";
        UrlMapping urlMapping = UrlMapping.builder()
                .id(1L)
                .shortCode(shortCode)
                .originalUrl("https://example.com")
                .createdAt(LocalDateTime.now())
                .clickCount(0L)
                .build();

        when(urlMappingRepository.findByShortCode(shortCode)).thenReturn(Optional.of(urlMapping));

        // When
        urlShortenerService.recordClick(shortCode);

        // Then
        verify(urlMappingRepository, times(1)).save(any(UrlMapping.class));
    }

    @Test
    void recordClick_throwsException() {
        // Given
        String shortCode = "abc123";
        when(urlMappingRepository.findByShortCode(shortCode)).thenReturn(Optional.empty());

        // When
        assertThrows(RuntimeException.class, () -> urlShortenerService.recordClick(shortCode));
    }
}