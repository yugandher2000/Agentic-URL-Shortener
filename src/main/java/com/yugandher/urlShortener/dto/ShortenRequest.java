package com.yugandher.urlShortener.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class ShortenRequest {

    @NotBlank(message = "URL must not be blank")
    @Pattern(
        regexp = "^https?://.*",
        message = "URL must start with http:// or https://"
    )
    private String longUrl;
}
