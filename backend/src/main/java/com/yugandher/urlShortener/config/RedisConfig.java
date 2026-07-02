package com.yugandher.urlShortener.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;

/**
 * Configures TWO Redis connection pools:
 *
 *   masterRedisTemplate  → connects to Redis MASTER  (all WRITES go here)
 *   replicaRedisTemplate → connects to Redis REPLICA (all READS  come from here)
 *
 * In Docker Compose both are pulled from Docker Hub (redis:7-alpine).
 * Locally, master is on :6379 and replica on :6380.
 */
@Configuration
public class RedisConfig {

    @Bean(name = "masterRedisTemplate")
    public StringRedisTemplate masterRedisTemplate(
            @Value("${spring.data.redis.host:localhost}") String host,
            @Value("${spring.data.redis.port:6379}") int port) {

        LettuceConnectionFactory factory = new LettuceConnectionFactory(host, port);
        factory.afterPropertiesSet();
        StringRedisTemplate template = new StringRedisTemplate(factory);
        template.afterPropertiesSet();
        return template;
    }

    @Bean(name = "replicaRedisTemplate")
    public StringRedisTemplate replicaRedisTemplate(
            @Value("${app.redis.replica.host:localhost}") String host,
            @Value("${app.redis.replica.port:6380}") int port) {

        LettuceConnectionFactory factory = new LettuceConnectionFactory(host, port);
        factory.afterPropertiesSet();
        StringRedisTemplate template = new StringRedisTemplate(factory);
        template.afterPropertiesSet();
        return template;
    }
}
