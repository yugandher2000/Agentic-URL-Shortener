
import com.yugandher.urlShortener.model.ShortenRequest;
import com.yugandher.urlShortener.model.ShortenResponse;
import com.yugandher.urlShortener.model.AnalyticsResponse;
import com.yugandher.urlShortener.service.UrlShortenerService;
import com.yugandher.urlShortener.properties.AppProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;

import javax.validation.Valid;

@RestController
@CrossOrigin(origins = "*")
@RequestMapping("/")
@RequiredArgsConstructor
public class UrlShortenerController {

    private final UrlShortenerService urlShortenerService;
    private final AppProperties appProperties;

    @PostMapping("/api/shorten")
    public ResponseEntity<ShortenResponse> shortenUrl(@Valid @RequestBody ShortenRequest shortenRequest) {
        String shortCode = urlShortenerService.shortenUrl(shortenRequest.getOriginalUrl());
        String shortUrl = ServletUriComponentsBuilder.fromCurrentContextPath()
                .path(appProperties.getBaseUrl() + "/{shortCode}")
                .buildAndExpand(shortCode)
                .toUriString();
        return ResponseEntity.status(HttpStatus.CREATED).body(new ShortenResponse(shortUrl));
    }

    @GetMapping("/{shortCode}")
    public ResponseEntity<Void> redirectUrl(@PathVariable String shortCode) {
        urlShortenerService.recordClick(shortCode);
        String originalUrl = urlShortenerService.getOriginalUrl(shortCode);
        return ResponseEntity.status(HttpStatus.FOUND)
                .header("Location", originalUrl)
                .build();
    }

    @GetMapping("/api/analytics/{shortCode}")
    public ResponseEntity<AnalyticsResponse> getAnalytics(@PathVariable String shortCode) {
        Long clickCount = urlShortenerService.getClickCount(shortCode);
        return ResponseEntity.ok(new AnalyticsResponse(clickCount));
    }
}