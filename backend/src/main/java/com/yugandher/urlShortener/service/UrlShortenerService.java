
import com.yugandher.urlShortener.model.UrlMapping;
import com.yugandher.urlShortener.repository.UrlMappingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.Base64Utils;

import javax.crypto.MessageDigest;
import javax.crypto.NoSuchAlgorithmException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigestSpi;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
public class UrlShortenerService {

    private final UrlMappingRepository urlMappingRepository;
    private final StringRedisTemplate masterRedisTemplate;
    private final StringRedisTemplate replicaRedisTemplate;
    private final ApplicationProperties props;

    public String shortenUrl(String originalUrl) {
        UrlMapping existingUrlMapping = urlMappingRepository.findByOriginalUrl(originalUrl);
        if (existingUrlMapping != null) {
            return props.getUrlBaseUrl() + existingUrlMapping.getShortCode();
        }

        UrlMapping urlMapping = new UrlMapping();
        urlMapping.setOriginalUrl(originalUrl);
        urlMapping.setCreatedAt(LocalDateTime.now());
        urlMapping.setClickCount(0L);

        String shortCode = generateShortCode(urlMapping);
        urlMapping.setShortCode(shortCode);

        urlMappingRepository.save(urlMapping);
        masterRedisTemplate.opsForValue().set(getRedisKey(shortCode), originalUrl, props.getCacheTtlSeconds(), TimeUnit.SECONDS);

        return props.getUrlBaseUrl() + shortCode;
    }

    public String getOriginalUrl(String shortCode) {
        String originalUrl = replicaRedisTemplate.opsForValue().get(getRedisKey(shortCode));
        if (originalUrl != null) {
            return originalUrl;
        }

        UrlMapping urlMapping = urlMappingRepository.findByShortCode(shortCode);
        if (urlMapping == null) {
            throw new UrlNotFoundException("URL not found");
        }

        masterRedisTemplate.opsForValue().set(getRedisKey(shortCode), urlMapping.getOriginalUrl(), props.getCacheTtlSeconds(), TimeUnit.SECONDS);
        return urlMapping.getOriginalUrl();
    }

    public void recordClick(String shortCode) {
        urlMappingRepository.incrementClickCount(shortCode);
    }

    public UrlMapping getAnalytics(String shortCode) {
        return urlMappingRepository.findByShortCode(shortCode);
    }

    private String generateShortCode(UrlMapping urlMapping) {
        long value = urlMapping.getId() != null ? urlMapping.getId() : System.currentTimeMillis();
        value = value & Long.MAX_VALUE;

        String base62String = Base62.encode(value);
        String shortCode = base62String.substring(0, props.getUrlCodeLength());

        if (urlMappingRepository.findByShortCode(shortCode) != null) {
            shortCode = generateShortCodeWithSuffix(urlMapping, shortCode);
        }

        return shortCode;
    }

    private String generateShortCodeWithSuffix(UrlMapping urlMapping, String shortCode) {
        int suffix = 1;
        while (urlMappingRepository.findByShortCode(shortCode + suffix) != null) {
            suffix++;
        }

        return shortCode + suffix;
    }

    private String getRedisKey(String shortCode) {
        return "url:" + shortCode;
    }
}
