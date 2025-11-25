"""
Adaptive rate limiting and backoff for NHS Terminology Server
Implements intelligent request throttling and error recovery
"""

import time
import random
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Backoff strategy types"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_second: float = 10.0
    max_concurrent_requests: int = 20
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay: float = 0.1
    max_delay: float = 30.0
    max_retries: int = 3
    jitter_enabled: bool = True
    adaptive_enabled: bool = True


@dataclass
class RequestStats:
    """Statistics for request tracking"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    average_response_time: float = 0.0
    last_request_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on server responses
    and implements exponential backoff for failed requests
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.stats = RequestStats()
        self._lock = threading.RLock()
        self._request_times = []
        self._active_requests = 0
        self._last_rate_limit_time: Optional[datetime] = None
        self._current_delay = self.config.base_delay
        self._retry_counts: Dict[str, int] = {}
        
        # Adaptive parameters
        self._dynamic_rate = self.config.requests_per_second
        self._server_load_factor = 1.0  # 1.0 = normal, >1.0 = overloaded
        
    def should_wait(self, request_id: Optional[str] = None) -> tuple[bool, float]:
        """
        Check if request should wait and return wait time
        
        Returns:
            (should_wait, wait_time_seconds)
        """
        with self._lock:
            now = datetime.now()
            
            # Check concurrent request limit
            if self._active_requests >= self.config.max_concurrent_requests:
                return True, self._calculate_backoff_delay()
            
            # Clean old request times (keep last second)
            cutoff = now - timedelta(seconds=1)
            self._request_times = [t for t in self._request_times if t > cutoff]
            
            # Check rate limit
            requests_last_second = len(self._request_times)
            if requests_last_second >= self._dynamic_rate:
                wait_time = 1.0 / self._dynamic_rate
                return True, wait_time
            
            # Check if we're in backoff period due to recent failures
            if self._should_backoff():
                backoff_delay = self._calculate_backoff_delay()
                return True, backoff_delay
            
            return False, 0.0
    
    def wait_if_needed(self, request_id: Optional[str] = None) -> float:
        """
        Wait if rate limiting is needed
        
        Returns:
            Time waited in seconds
        """
        should_wait, wait_time = self.should_wait(request_id)
        
        if should_wait and wait_time > 0:
            # Add jitter to prevent thundering herd
            if self.config.jitter_enabled:
                jitter = random.uniform(0, min(wait_time * 0.1, 0.5))
                wait_time += jitter
            
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s (request_id: {request_id})")
            time.sleep(wait_time)
            return wait_time
        
        return 0.0
    
    def record_request_start(self, request_id: Optional[str] = None):
        """Record the start of a request"""
        with self._lock:
            self._active_requests += 1
            self._request_times.append(datetime.now())
            self.stats.total_requests += 1
            self.stats.last_request_time = datetime.now()
    
    def record_request_end(self, request_id: Optional[str] = None, 
                          response_time: float = 0.0,
                          status_code: Optional[int] = None,
                          success: bool = True):
        """Record the end of a request with outcome"""
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            
            # Update response time statistics
            if response_time > 0:
                total_time = self.stats.average_response_time * self.stats.successful_requests
                self.stats.average_response_time = (total_time + response_time) / (self.stats.successful_requests + 1)
            
            # Update success/failure statistics
            if success:
                self.stats.successful_requests += 1
                self.stats.consecutive_successes += 1
                self.stats.consecutive_failures = 0
                
                # Gradually reduce delay on success
                if self.config.adaptive_enabled:
                    self._current_delay = max(
                        self.config.base_delay,
                        self._current_delay * 0.9
                    )
                    
            else:
                self.stats.failed_requests += 1
                self.stats.consecutive_failures += 1
                self.stats.consecutive_successes = 0
                
                # Increase delay on failure
                if self.config.adaptive_enabled:
                    self._current_delay = min(
                        self.config.max_delay,
                        self._current_delay * 2
                    )
            
            # Handle specific status codes
            if status_code:
                self._handle_status_code(status_code, request_id)
            
            # Adaptive rate adjustment
            if self.config.adaptive_enabled:
                self._adjust_rate_adaptively(success, status_code, response_time)
    
    def record_rate_limit_hit(self, retry_after: Optional[float] = None):
        """Record that we hit a rate limit"""
        with self._lock:
            self.stats.rate_limited_requests += 1
            self._last_rate_limit_time = datetime.now()
            
            if retry_after:
                self._current_delay = min(self.config.max_delay, retry_after)
            
            # Reduce rate when we hit rate limits
            if self.config.adaptive_enabled:
                self._dynamic_rate = max(1.0, self._dynamic_rate * 0.5)
                logger.info(f"Rate limit hit, reducing rate to {self._dynamic_rate:.1f} req/s")
    
    def _should_backoff(self) -> bool:
        """Check if we should apply backoff due to recent failures"""
        if self.stats.consecutive_failures >= 3:
            return True
        
        if self._last_rate_limit_time:
            time_since_rate_limit = datetime.now() - self._last_rate_limit_time
            if time_since_rate_limit.total_seconds() < self._current_delay:
                return True
        
        return False
    
    def _calculate_backoff_delay(self) -> float:
        """Calculate backoff delay based on current strategy"""
        if self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (2 ** min(self.stats.consecutive_failures, 10))
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * (1 + self.stats.consecutive_failures)
        else:  # FIXED
            delay = self.config.base_delay
        
        return min(delay, self.config.max_delay)
    
    def _handle_status_code(self, status_code: int, request_id: Optional[str]):
        """Handle specific HTTP status codes"""
        if status_code == 429:  # Too Many Requests
            self.record_rate_limit_hit()
        elif status_code in [502, 503, 504]:  # Server errors
            # Server overload indicators
            if self.config.adaptive_enabled:
                self._server_load_factor = min(5.0, self._server_load_factor * 1.5)
                self._dynamic_rate = max(1.0, self.config.requests_per_second / self._server_load_factor)
        elif 200 <= status_code < 300:  # Success
            # Server recovering
            if self.config.adaptive_enabled:
                self._server_load_factor = max(1.0, self._server_load_factor * 0.95)
                self._dynamic_rate = min(
                    self.config.requests_per_second,
                    self.config.requests_per_second / self._server_load_factor
                )
    
    def _adjust_rate_adaptively(self, success: bool, status_code: Optional[int], response_time: float):
        """Adjust request rate based on server performance indicators"""
        if not self.config.adaptive_enabled:
            return
        
        # Adjust based on response time
        if response_time > 0:
            if response_time > 5.0:  # Slow responses
                self._dynamic_rate = max(1.0, self._dynamic_rate * 0.9)
            elif response_time < 1.0 and success:  # Fast responses
                self._dynamic_rate = min(
                    self.config.requests_per_second,
                    self._dynamic_rate * 1.05
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics"""
        with self._lock:
            success_rate = (
                self.stats.successful_requests / self.stats.total_requests * 100
                if self.stats.total_requests > 0 else 0
            )
            
            return {
                'total_requests': self.stats.total_requests,
                'successful_requests': self.stats.successful_requests,
                'failed_requests': self.stats.failed_requests,
                'rate_limited_requests': self.stats.rate_limited_requests,
                'success_rate': f"{success_rate:.1f}%",
                'average_response_time': f"{self.stats.average_response_time:.2f}s",
                'consecutive_failures': self.stats.consecutive_failures,
                'consecutive_successes': self.stats.consecutive_successes,
                'current_dynamic_rate': f"{self._dynamic_rate:.1f} req/s",
                'current_delay': f"{self._current_delay:.2f}s",
                'server_load_factor': f"{self._server_load_factor:.2f}",
                'active_requests': self._active_requests,
                'last_request_time': self.stats.last_request_time.isoformat() if self.stats.last_request_time else None
            }
    
    def reset_stats(self):
        """Reset all statistics"""
        with self._lock:
            self.stats = RequestStats()
            self._request_times.clear()
            self._retry_counts.clear()
            self._current_delay = self.config.base_delay
            self._dynamic_rate = self.config.requests_per_second
            self._server_load_factor = 1.0


class RequestTracker:
    """Track individual request retry attempts"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self._attempts: Dict[str, int] = {}
        self._lock = threading.Lock()
    
    def can_retry(self, request_id: str) -> bool:
        """Check if request can be retried"""
        with self._lock:
            attempts = self._attempts.get(request_id, 0)
            return attempts < self.max_retries
    
    def record_attempt(self, request_id: str) -> int:
        """Record a retry attempt and return current attempt number"""
        with self._lock:
            attempts = self._attempts.get(request_id, 0) + 1
            self._attempts[request_id] = attempts
            return attempts
    
    def clear_request(self, request_id: str):
        """Clear tracking for completed request"""
        with self._lock:
            self._attempts.pop(request_id, None)
    
    def get_attempt_count(self, request_id: str) -> int:
        """Get current attempt count for request"""
        with self._lock:
            return self._attempts.get(request_id, 0)


# Global instances
_default_rate_limiter = AdaptiveRateLimiter()
_default_request_tracker = RequestTracker()


def get_rate_limiter() -> AdaptiveRateLimiter:
    """Get the global rate limiter instance"""
    return _default_rate_limiter


def get_request_tracker() -> RequestTracker:
    """Get the global request tracker instance"""
    return _default_request_tracker


def configure_rate_limiting(config: RateLimitConfig):
    """Configure the global rate limiter"""
    global _default_rate_limiter
    _default_rate_limiter = AdaptiveRateLimiter(config)


def reset_rate_limiting():
    """Reset rate limiting to defaults"""
    global _default_rate_limiter, _default_request_tracker
    _default_rate_limiter = AdaptiveRateLimiter()
    _default_request_tracker = RequestTracker()