# NHS Terminology Server Integration - Technical Guide

## Architecture Overview

ClinXML's NHS terminology server integration implements enterprise-grade reliability patterns designed for healthcare environments, featuring structured error handling, adaptive rate limiting, thread-safe operations, and intelligent progress tracking.

## Core Architecture Components

### Service Layer Structure
```
expansion_ui.py (Streamlit UI)
    ↓ User interactions
expansion_service.py (Business logic)
    ↓ Service coordination  
nhs_terminology_client.py (NHS API client)
    ↓ FHIR R4 operations
rate_limiter.py (Adaptive throttling)
progress_tracker.py (Time estimation)
    ↓ Infrastructure
error_handling.py (Structured errors)
```

### Module Responsibilities

**`expansion_ui.py`**: Streamlit interface with fragment-based rendering for responsive UI updates
**`expansion_service.py`**: UI-independent business logic with multi-tier caching
**`nhs_terminology_client.py`**: Thread-safe NHS API client with OAuth2 management
**`rate_limiter.py`**: Adaptive request throttling with exponential backoff
**`progress_tracker.py`**: Intelligent time estimation with performance analytics
**`error_handling.py`**: Structured exception hierarchy with healthcare context

## Reliability Infrastructure

### Enhanced Error Handling System

**Location**: `utils/terminology_server/nhs_terminology_client.py`, `utils/common/error_handling.py`

#### TerminologyServerError Class
```python
class TerminologyServerError(EMISConverterError):
    def __init__(self, message: str, error_type: str = None, 
                 api_response: Optional[Dict] = None, 
                 user_guidance: Optional[str] = None):
        self.error_type = error_type
        self.api_response = api_response
        self.user_guidance = user_guidance
        super().__init__(message)
```

#### Error Classification and Recovery
```python
# Error type mapping for structured handling
ERROR_TYPE_MAPPING = {
    401: ("authentication_failed", "NHS Terminology Server credentials invalid"),
    404: ("code_not_found", "SNOMED code does not exist in terminology server"),
    422: ("invalid_request", "Invalid concept expansion request format"),
    429: ("rate_limited", "Request rate too high - backing off"),
    500: ("server_error", "NHS Terminology Server experiencing issues")
}
```

### Adaptive Rate Limiting

**Location**: `utils/terminology_server/rate_limiter.py`

#### RateLimitConfig
```python
@dataclass
class RateLimitConfig:
    requests_per_second: float = 2.0
    burst_size: int = 5
    backoff_factor: float = 2.0
    max_backoff: float = 60.0
    jitter: bool = True
```

#### AdaptiveRateLimiter Implementation
```python
class AdaptiveRateLimiter:
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._dynamic_rate = self.config.requests_per_second
        self._consecutive_errors = 0
        self._last_success = time.time()
    
    async def acquire_slot(self):
        """Acquire permission to make request with adaptive delay"""
        current_delay = self._calculate_delay()
        if current_delay > 0:
            await asyncio.sleep(current_delay)
    
    def _calculate_delay(self) -> float:
        """Calculate adaptive delay based on recent performance"""
        base_delay = 1.0 / self._dynamic_rate
        
        if self._consecutive_errors > 0:
            # Exponential backoff with jitter
            backoff_delay = min(
                base_delay * (self.config.backoff_factor ** self._consecutive_errors),
                self.config.max_backoff
            )
            
            if self.config.jitter:
                backoff_delay *= (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
            
            return backoff_delay
        
        return base_delay
```

### Thread Safety and Concurrency

**Location**: `utils/terminology_server/nhs_terminology_client.py`

#### ThreadSafeTokenManager
```python
class ThreadSafeTokenManager:
    def __init__(self, credentials: CredentialConfig):
        self._lock = threading.RLock()
        self._token_cache: Dict[str, TokenInfo] = {}
        self._credentials = credentials
    
    def get_valid_token(self) -> str:
        """Get valid token with thread-safe refresh"""
        with self._lock:
            credential_hash = self._hash_credentials()
            token_info = self._token_cache.get(credential_hash)
            
            if not token_info or self._is_token_expired(token_info):
                token_info = self._refresh_token()
                self._token_cache[credential_hash] = token_info
            
            return token_info.access_token
```

#### Worker Pool Management
```python
def _get_optimal_worker_count(self, code_count: int) -> int:
    """Calculate optimal worker count based on workload"""
    if code_count <= 100:
        return 8   # Conservative for small workloads
    elif code_count <= 300:
        return 12  # Moderate for medium workloads
    elif code_count <= 500:
        return 16  # High for large workloads
    else:
        return 20  # Maximum for very large workloads
```

### Advanced Progress Tracking

**Location**: `utils/terminology_server/progress_tracker.py`

#### AdaptiveTimeEstimator
```python
class AdaptiveTimeEstimator:
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self._timing_samples: List[float] = []
        self._lock = threading.Lock()
        self.base_estimate_per_item = 0.1  # Realistic 100ms per API call
    
    def _calculate_adaptive_estimate(self) -> float:
        """Calculate adaptive time estimate using recent performance"""
        if not self._timing_samples:
            return self.base_estimate_per_item
        
        # Get recent samples (last 10 most relevant for current conditions)
        recent_samples = self._timing_samples[-10:] if len(self._timing_samples) > 10 else self._timing_samples
        
        if len(recent_samples) >= 3:
            recent_average = sum(recent_samples) / len(recent_samples)
            # Cap unreasonably high estimates (network hiccups)
            return min(recent_average, 5.0)
        
        # Fallback to simple average with cap
        simple_average = sum(self._timing_samples) / len(self._timing_samples)
        return min(simple_average, 3.0)
```

#### ProgressMetrics Data Structure
```python
@dataclass
class ProgressMetrics:
    total_items: int
    completed_items: int
    failed_items: int
    successful_items: int
    current_item: Optional[str] = None
    estimated_total_time: Optional[float] = None
    estimated_remaining_time: Optional[float] = None
    elapsed_time: float = 0.0
    items_per_second: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
```

## Multi-Tier Caching Strategy

### Cache Hierarchy
```
UI Request
    ↓
1. Session State Cache (fastest - in memory)
    ↓ Cache miss
2. Individual Lookup Cache (persistent across refreshes)
    ↓ Cache miss  
3. EMIS Integration Cache (GitHub → local → API fallback)
    ↓ Cache miss
4. NHS Terminology Server (live API call with rate limiting)
```

### Cache Implementation

#### Session State Caching
```python
def _cache_expansion_result(self, result: ExpansionResult, include_inactive: bool = False):
    """Cache expansion result in session state"""
    cache_key = self._get_cache_key(result.source_code, include_inactive)
    
    # Convert result to dict with proper datetime handling
    result_dict = asdict(result)
    if isinstance(result_dict['expansion_timestamp'], datetime):
        result_dict['expansion_timestamp'] = result_dict['expansion_timestamp'].isoformat()
    
    st.session_state[cache_key] = {
        'result': result_dict,
        'cached_at': datetime.now().isoformat()
    }
```

#### Individual Lookup Persistence
```python
# Persistent cache for individual code lookups
if 'individual_lookup_results' not in st.session_state:
    st.session_state.individual_lookup_results = {}

# Store with persistence across refreshes
st.session_state.individual_lookup_results[snomed_code.strip()] = {
    'result': result,
    'include_inactive': include_inactive,
    'lookup_time': datetime.now(),
    'cached': use_cache
}
```

## NHS England Terminology Server API Integration

### OAuth2 System-to-System Authentication

#### Authentication Flow
```python
async def authenticate(self) -> TokenInfo:
    """Authenticate with NHS England using OAuth2 client credentials"""
    auth_data = {
        'grant_type': 'client_credentials',
        'client_id': self.credentials.client_id,
        'client_secret': self.credentials.client_secret
    }
    
    response = await self._post_request(
        f"{self.credentials.auth_url}/token",
        data=auth_data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    return TokenInfo(
        access_token=response['access_token'],
        token_type=response['token_type'],
        expires_in=response['expires_in'],
        issued_at=datetime.now()
    )
```

### FHIR R4 API Operations

#### Concept Expansion with ECL
```python
def expand_concept(self, snomed_code: str, include_inactive: bool = False) -> ExpansionResult:
    """Expand SNOMED concept using FHIR ValueSet $expand operation"""
    
    # Build ECL (Expression Constraint Language) query
    ecl_expression = f"< {snomed_code}"  # All descendants
    
    params = {
        'url': f'http://snomed.info/sct?fhir_vs=ecl/{ecl_expression}',
        '_format': 'json',
        'count': '1000',  # Pagination limit
        'offset': '0',
        'activeOnly': 'false' if include_inactive else 'true'
    }
    
    response = self._make_request('GET', '/ValueSet/$expand', params=params)
    return self._parse_expansion_response(response, snomed_code)
```

#### Request/Response Handling
```python
def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
    """Make authenticated request with error handling"""
    headers = {
        'Authorization': f'Bearer {self.token_manager.get_valid_token()}',
        'Accept': 'application/fhir+json',
        'Content-Type': 'application/fhir+json'
    }
    
    try:
        response = requests.request(
            method=method,
            url=f"{self.credentials.base_url}{endpoint}",
            headers=headers,
            timeout=self.config.request_timeout,
            **kwargs
        )
        
        # Handle common HTTP status codes
        if response.status_code == 401:
            # Token expired - trigger refresh
            self.token_manager.invalidate_token()
            raise TerminologyServerError(
                "Authentication failed - token refresh required",
                error_type="authentication_failed"
            )
        elif response.status_code == 404:
            raise TerminologyServerError(
                "SNOMED code does not exist in terminology server",
                error_type="code_not_found"
            )
        elif response.status_code == 422:
            raise TerminologyServerError(
                "Invalid concept expansion request format",
                error_type="invalid_request"
            )
        elif response.status_code >= 500:
            raise TerminologyServerError(
                "NHS Terminology Server experiencing issues",
                error_type="server_error"
            )
        
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        raise TerminologyServerError(
            f"Connection error: {str(e)}",
            error_type="network_error"
        )
```

## Performance Optimisation Strategies

### Worker Scaling Algorithm
```python
def _calculate_worker_allocation(self, total_codes: int) -> Dict[str, int]:
    """Calculate optimal worker allocation based on workload characteristics"""
    
    # Base worker count determination
    if total_codes <= 100:
        base_workers = 8   # Conservative for small loads
    elif total_codes <= 300:
        base_workers = 12  # Moderate scaling
    elif total_codes <= 500:
        base_workers = 16  # Aggressive for large loads
    else:
        base_workers = 20  # Maximum concurrent workers
    
    # Adjust for cached vs uncached ratio
    cached_ratio = self._get_cache_hit_ratio(total_codes)
    adjusted_workers = max(1, int(base_workers * (1 - cached_ratio)))
    
    return {
        'total_workers': min(adjusted_workers, total_codes),
        'batch_size': max(1, total_codes // adjusted_workers),
        'expected_duration': self._estimate_completion_time(total_codes, adjusted_workers)
    }
```

### Memory Management
```python
def _cleanup_worker_resources(self, threads: List[threading.Thread]):
    """Clean up worker threads and associated resources"""
    for thread in threads:
        if thread.is_alive():
            # Graceful termination attempt
            thread.join(timeout=1.0)
    
    # Force garbage collection after batch processing
    import gc
    gc.collect()
```

## Error Recovery and Resilience

### Exponential Backoff Implementation
```python
class BackoffStrategy:
    def __init__(self, base_delay: float = 0.5, max_delay: float = 60.0, factor: float = 2.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = min(self.base_delay * (self.factor ** attempt), self.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.5, 1.5)
        return delay * jitter
```

### Graceful Degradation
```python
def handle_partial_failure(self, successful_results: List, failed_codes: List) -> ExpansionSummary:
    """Handle scenarios where some codes succeed and others fail"""
    
    # Continue processing successful results
    processed_children = []
    for result in successful_results:
        if result and not result.error:
            processed_children.extend(self._process_children(result))
    
    # Log failed codes for debugging
    if failed_codes:
        logger.warning(f"Failed to expand {len(failed_codes)} codes: {failed_codes[:5]}...")
    
    return ExpansionSummary(
        total_requested=len(successful_results) + len(failed_codes),
        successful_expansions=len(successful_results),
        failed_expansions=len(failed_codes),
        total_child_codes=len(processed_children),
        partial_success=len(failed_codes) > 0
    )
```

## Configuration and Deployment

### Environment Configuration
```python
@dataclass
class EnvironmentConfig:
    # NHS England Terminology Server endpoints
    production_base_url: str = "https://ontology.nhs.uk/authoring/fhir"
    production_auth_url: str = "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"
    
    # Request timeouts and limits
    request_timeout: int = 30
    token_refresh_buffer: int = 300  # Refresh 5 minutes before expiry
    max_concurrent_workers: int = 20
    
    # Rate limiting defaults
    default_requests_per_second: float = 2.0
    burst_allowance: int = 5
    
    # Progress tracking settings
    progress_update_interval: float = 0.25  # 250ms updates
    time_estimation_window: int = 50  # Recent samples for estimation
```

### Deployment Considerations

#### Streamlit Cloud Compatibility
- **Memory Constraints**: Worker scaling respects ~2.7GB Streamlit Cloud limits
- **Session State**: Efficient caching prevents memory bloat
- **Request Limits**: Rate limiting prevents API quota exhaustion

#### Enterprise Deployment
- **Credential Security**: Support for environment variable injection
- **Logging Integration**: Structured logging compatible with enterprise monitoring
- **Audit Compliance**: Request tracking for healthcare compliance requirements

## Testing and Validation

### Unit Test Structure
```python
class TestNHSTerminologyClient:
    @pytest.fixture
    def mock_client(self):
        """Create client with mocked dependencies"""
        credentials = CredentialConfig(
            client_id="test_id",
            client_secret="test_secret"
        )
        return NHSTerminologyServerClient(credentials)
    
    @pytest.mark.asyncio
    async def test_expand_concept_success(self, mock_client):
        """Test successful concept expansion"""
        with patch('requests.request') as mock_request:
            mock_request.return_value.status_code = 200
            mock_request.return_value.json.return_value = self._mock_fhir_response()
            
            result = await mock_client.expand_concept("73211009")
            
            assert result.success
            assert len(result.children) > 0
            assert result.source_code == "73211009"
```

### Integration Test Scenarios
```python
class TestIntegrationScenarios:
    def test_large_hierarchy_expansion(self):
        """Test expansion of concept with many children"""
        # Test with SNOMED codes known to have large hierarchies
        
    def test_network_resilience(self):
        """Test behavior under network conditions"""
        # Simulate timeouts, connection errors, server errors
        
    def test_concurrent_expansion(self):
        """Test thread safety under concurrent load"""
        # Multiple simultaneous expansion requests
```

## Monitoring and Observability

### Performance Metrics
```python
@dataclass
class PerformanceMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    cache_hit_ratio: float = 0.0
    worker_utilization: float = 0.0
    
    def success_rate(self) -> float:
        return self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
```

### Logging Strategy
```python
import structlog

logger = structlog.get_logger("nhs_terminology")

# Structured logging for observability
logger.info(
    "expansion_started",
    code_count=len(codes),
    worker_count=worker_allocation['total_workers'],
    cache_hit_ratio=cache_stats['hit_ratio']
)
```

## Security Considerations

### Credential Management
- **Environment Isolation**: Credentials never logged or exposed in error messages
- **Token Security**: Access tokens stored only in memory, cleared on expiry
- **Request Security**: All API calls use HTTPS with proper certificate validation

### Data Protection
- **No PHI Transmission**: Only SNOMED codes sent to NHS servers
- **Session Isolation**: Per-session credential and cache management
- **Audit Logging**: Connection attempts logged for compliance without credential exposure

---

This technical guide provides comprehensive implementation details for developers maintaining and extending the NHS terminology server integration in healthcare environments.