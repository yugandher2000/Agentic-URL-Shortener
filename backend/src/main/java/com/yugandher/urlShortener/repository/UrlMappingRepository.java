package com.yugandher.urlShortener.repository;

import com.yugandher.urlShortener.model.UrlMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface UrlMappingRepository extends JpaRepository<UrlMapping, Long> {

    Optional<UrlMapping> findByShortCode(String shortCode);

    Optional<UrlMapping> findByOriginalUrl(String originalUrl);

    @Modifying
    @Query("UPDATE UrlMapping u SET u.clickCount = u.clickCount+1 WHERE u.shortCode=:s")
    void incrementClickCount(@Param("s") String shortCode);
}