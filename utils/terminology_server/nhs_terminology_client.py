"""
Improved NHS England Terminology Server Client

Enhanced version with:
- Structured error handling with user-friendly messages
- Adaptive rate limiting and exponential backoff
- Thread-safe operations
- Secure credential handling
- Better progress tracking
"""

import requests
import json
import time
import uuid
import threading
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import quote
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from ..common.error_handling import (
    TerminologyServerError, get_error_handler, ErrorSeverity, ErrorContext
)
from .rate_limiter import (
    get_rate_limiter, get_request_tracker, RateLimitConfig, 
    configure_rate_limiting, BackoffStrategy
)
logger = logging.getLogger(__name__)


@dataclass
class ExpandedConcept:
    """Represents an expanded SNOMED concept from the terminology server"""
    code: str
    display: str
    system: str = "http://snomed.info/sct"
    inactive: bool = False
    parent_code: Optional[str] = None


@dataclass
class ExpansionResult:
    """Result of a terminology expansion operation"""
    source_code: str
    source_display: str
    children: List[ExpandedConcept]
    total_count: int
    expansion_timestamp: datetime
    error: Optional[str] = None


@dataclass
class CredentialConfig:
    """Configuration for NHS Terminology Server credentials"""
    client_id: str
    client_secret: str
    base_url: str = "https://ontology.nhs.uk/production1/fhir"
    auth_url: str = "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"


@dataclass 
class ClientConfig:
    """Configuration for the improved NHS client"""
    request_timeout: int = 30
    token_refresh_buffer_minutes: int = 5
    max_expansion_results: int = 50000
    batch_size: int = 1000
    debug_mode: bool = False
    enable_caching: bool = True


class ThreadSafeTokenManager:
    """Thread-safe token management for concurrent requests"""
    
    def __init__(self, credentials: CredentialConfig):
        self.credentials = credentials
        self.access_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self._lock = threading.RLock()
        self._authenticating = False
        
    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary"""
        with self._lock:
            if self._is_token_valid():
                return self.access_token
                
            # If already authenticating in another thread, wait
            if self._authenticating:
                return self._wait_for_authentication()
                
            # Perform authentication
            return self._authenticate()
    
    def _is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.access_token or not self.token_expires:
            return False
        buffer = timedelta(minutes=5)
        return datetime.now() < (self.token_expires - buffer)
    
    def _wait_for_authentication(self) -> Optional[str]:
        """Wait for ongoing authentication to complete"""
        max_wait = 30  # seconds
        start_time = time.time()
        
        while self._authenticating and (time.time() - start_time) < max_wait:
            time.sleep(0.1)
            
        return self.access_token if self._is_token_valid() else None
    
    def _authenticate(self) -> Optional[str]:
        """Perform authentication with the NHS Terminology Server"""
        self._authenticating = True
        
        try:
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.credentials.client_id,
                'client_secret': self.credentials.client_secret
            }
            
            response = requests.post(
                self.credentials.auth_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 1800)
                self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("Successfully authenticated with NHS Terminology Server")
                return self.access_token
            
            elif response.status_code == 401:
                raise TerminologyServerError(
                    "Authentication failed: Invalid credentials",
                    error_type="authentication_failed",
                    api_response={'status_code': response.status_code, 'response': response.text},
                    user_guidance="Please check your NHS Terminology Server credentials in the application settings."
                )
            
            elif response.status_code == 429:
                raise TerminologyServerError(
                    "Authentication rate limited",
                    error_type="rate_limit_exceeded", 
                    api_response={'status_code': response.status_code},
                    user_guidance="Too many authentication attempts. Please wait a few minutes and try again."
                )
            
            else:
                raise TerminologyServerError(
                    f"Authentication failed with status {response.status_code}",
                    error_type="server_error",
                    api_response={'status_code': response.status_code, 'response': response.text},
                    user_guidance="NHS Terminology Server authentication is currently unavailable. Please try again later."
                )
                
        except requests.exceptions.Timeout:
            raise TerminologyServerError(
                "Authentication request timed out",
                error_type="timeout_error",
                user_guidance="Connection to NHS Terminology Server timed out. Please check your internet connection and try again."
            )
        
        except requests.exceptions.ConnectionError:
            raise TerminologyServerError(
                "Cannot connect to NHS Terminology Server for authentication",
                error_type="connection_error",
                user_guidance="Cannot connect to NHS Terminology Server. Please check your internet connection."
            )
        
        except Exception as e:
            raise TerminologyServerError(
                f"Unexpected error during authentication: {str(e)}",
                error_type="server_error",
                user_guidance="An unexpected error occurred during authentication. Please try again."
            )
        
        finally:
            self._authenticating = False
    
    def invalidate_token(self):
        """Invalidate the current token to force re-authentication"""
        with self._lock:
            self.access_token = None
            self.token_expires = None


class NHSTerminologyServerClient:
    """
    NHS Terminology Server client with enhanced reliability features
    """
    
    def __init__(self, credentials: CredentialConfig, config: ClientConfig = None):
        self.credentials = credentials
        self.config = config or ClientConfig()
        self.token_manager = ThreadSafeTokenManager(credentials)
        self.error_handler = get_error_handler()
        self.rate_limiter = get_rate_limiter()
        self.request_tracker = get_request_tracker()
        
        # Configure rate limiting for NHS Terminology Server
        self._configure_rate_limiting()
        
        logger.info("Initialized improved NHS Terminology Server client")
    
    def _configure_rate_limiting(self):
        """Configure adaptive rate limiting for NHS server"""
        config = RateLimitConfig(
            requests_per_second=10.0,  # Conservative start
            max_concurrent_requests=20,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay=0.1,
            max_delay=30.0,
            max_retries=3,
            jitter_enabled=True,
            adaptive_enabled=True
        )
        configure_rate_limiting(config)
    
    def _make_request(self, endpoint: str, params: Dict = None, request_id: str = None) -> Tuple[Optional[Dict], Optional[TerminologyServerError]]:
        """
        Make authenticated request with proper error handling and rate limiting
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        start_time = time.time()
        
        try:
            # Apply rate limiting
            wait_time = self.rate_limiter.wait_if_needed(request_id)
            self.rate_limiter.record_request_start(request_id)
            
            # Get valid authentication token
            token = self.token_manager.get_valid_token()
            if not token:
                error = TerminologyServerError(
                    "Failed to obtain valid authentication token",
                    error_type="authentication_failed",
                    user_guidance="Unable to authenticate with NHS Terminology Server. Please check your credentials."
                )
                self.rate_limiter.record_request_end(request_id, success=False)
                return None, error
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/fhir+json',
                'Content-Type': 'application/fhir+json',
                'User-Agent': 'EMIS-XML-Converter/1.0'
            }
            
            url = f"{self.credentials.base_url}/{endpoint}"
            response = requests.get(
                url, 
                headers=headers, 
                params=params, 
                timeout=self.config.request_timeout
            )
            
            response_time = time.time() - start_time
            
            # Handle response
            if response.status_code == 200:
                self.rate_limiter.record_request_end(
                    request_id, response_time=response_time, 
                    status_code=response.status_code, success=True
                )
                
                try:
                    return response.json(), None
                except json.JSONDecodeError:
                    error = TerminologyServerError(
                        "Invalid JSON response from NHS Terminology Server",
                        error_type="malformed_response",
                        user_guidance="Received unexpected response format. Please try again."
                    )
                    return None, error
                    
            elif response.status_code == 401:
                # Token expired, invalidate and potentially retry
                self.token_manager.invalidate_token()
                
                if self.request_tracker.can_retry(request_id):
                    attempt = self.request_tracker.record_attempt(request_id)
                    logger.info(f"Retrying request {request_id} due to 401 (attempt {attempt})")
                    
                    # Recursive retry with fresh token
                    return self._make_request(endpoint, params, request_id)
                
                error = TerminologyServerError(
                    "Authentication token expired and retry failed",
                    error_type="authentication_failed",
                    user_guidance="Authentication session expired. Please try again."
                )
                self.rate_limiter.record_request_end(request_id, success=False, status_code=401)
                return None, error
                
            elif response.status_code == 404:
                error = TerminologyServerError(
                    "Resource not found on NHS Terminology Server",
                    error_type="code_not_found",
                    api_response={'status_code': response.status_code},
                    user_guidance="The SNOMED code was not found. Please check the code is correct and try again."
                )
                self.rate_limiter.record_request_end(request_id, success=False, status_code=404)
                return None, error
                
            elif response.status_code == 422:
                error = TerminologyServerError(
                    "Invalid request format or parameters",
                    error_type="invalid_code_format",
                    api_response={'status_code': response.status_code, 'response': response.text},
                    user_guidance="The request format or SNOMED code format is invalid. Please check your input."
                )
                self.rate_limiter.record_request_end(request_id, success=False, status_code=422)
                return None, error
                
            elif response.status_code == 429:
                # Rate limited
                retry_after = None
                if 'Retry-After' in response.headers:
                    try:
                        retry_after = float(response.headers['Retry-After'])
                    except ValueError:
                        pass
                
                self.rate_limiter.record_rate_limit_hit(retry_after)
                
                if self.request_tracker.can_retry(request_id):
                    attempt = self.request_tracker.record_attempt(request_id)
                    logger.info(f"Rate limited, retrying request {request_id} (attempt {attempt})")
                    
                    # Wait and retry
                    wait_time = retry_after or self.rate_limiter._calculate_backoff_delay()
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, request_id)
                
                error = TerminologyServerError(
                    "Rate limit exceeded and retry failed",
                    error_type="rate_limit_exceeded",
                    user_guidance="Too many requests to NHS Terminology Server. Please wait and try again."
                )
                return None, error
                
            elif response.status_code >= 500:
                self.rate_limiter.record_request_end(request_id, success=False, status_code=response.status_code)
                
                if self.request_tracker.can_retry(request_id):
                    attempt = self.request_tracker.record_attempt(request_id)
                    logger.info(f"Server error, retrying request {request_id} (attempt {attempt})")
                    
                    # Exponential backoff for server errors
                    backoff_time = min(30, 2 ** attempt)
                    time.sleep(backoff_time)
                    return self._make_request(endpoint, params, request_id)
                
                error = TerminologyServerError(
                    f"NHS Terminology Server error: {response.status_code}",
                    error_type="server_error",
                    api_response={'status_code': response.status_code},
                    user_guidance="NHS Terminology Server is experiencing issues. Please try again later."
                )
                return None, error
            
            else:
                # Other errors
                self.rate_limiter.record_request_end(request_id, success=False, status_code=response.status_code)
                error = TerminologyServerError(
                    f"Unexpected response: {response.status_code}",
                    error_type="server_error",
                    api_response={'status_code': response.status_code, 'response': response.text},
                    user_guidance="NHS Terminology Server returned an unexpected response. Please try again."
                )
                return None, error
                
        except requests.exceptions.Timeout:
            self.rate_limiter.record_request_end(request_id, success=False)
            error = TerminologyServerError(
                "Request to NHS Terminology Server timed out",
                error_type="timeout_error",
                user_guidance=f"Request timed out after {self.config.request_timeout} seconds. Please try again."
            )
            return None, error
            
        except requests.exceptions.ConnectionError:
            self.rate_limiter.record_request_end(request_id, success=False)
            error = TerminologyServerError(
                "Cannot connect to NHS Terminology Server",
                error_type="connection_error",
                user_guidance="Cannot connect to NHS Terminology Server. Please check your internet connection."
            )
            return None, error
            
        except Exception as e:
            self.rate_limiter.record_request_end(request_id, success=False)
            error = TerminologyServerError(
                f"Unexpected error during request: {str(e)}",
                error_type="server_error",
                user_guidance="An unexpected error occurred. Please try again."
            )
            return None, error
        
        finally:
            self.request_tracker.clear_request(request_id)
    
    def expand_concept(self, snomed_code: str, include_inactive: bool = False) -> ExpansionResult:
        """
        Expand a SNOMED concept with enhanced error handling
        """
        try:
            request_id = f"expand_{snomed_code}_{int(time.time())}"
            
            if self.config.debug_mode:
                logger.debug(f"Starting expansion for code: {snomed_code}")
            
            # First, get the source concept display name
            source_display = snomed_code
            lookup_result, lookup_error = self._lookup_concept_details(snomed_code)
            
            if lookup_error:
                return ExpansionResult(
                    source_code=snomed_code,
                    source_display=snomed_code,
                    children=[],
                    total_count=0,
                    expansion_timestamp=datetime.now(),
                    error=lookup_error.get_user_friendly_message()
                )
            
            if lookup_result and 'parameter' in lookup_result:
                for param in lookup_result.get('parameter', []):
                    if param.get('name') == 'display':
                        source_display = param.get('valueString', snomed_code)
                        break
            
            # Perform expansion with pagination
            all_children = []
            offset = 0
            total_count = 0
            
            while True:
                batch_result, batch_error = self._expand_concept_batch(
                    snomed_code, include_inactive, offset, self.config.batch_size
                )
                
                if batch_error:
                    if offset == 0:  # First batch failed
                        return ExpansionResult(
                            source_code=snomed_code,
                            source_display=source_display,
                            children=[],
                            total_count=0,
                            expansion_timestamp=datetime.now(),
                            error=batch_error.get_user_friendly_message()
                        )
                    else:
                        # Later batch failed, return what we have
                        break
                
                # Process batch results
                batch_children = []
                if batch_result and 'expansion' in batch_result:
                    expansion = batch_result['expansion']
                    
                    if offset == 0:
                        total_count = expansion.get('total', 0)
                    
                    if 'contains' in expansion:
                        for concept in expansion['contains']:
                            batch_children.append(ExpandedConcept(
                                code=concept.get('code', ''),
                                display=concept.get('display', ''),
                                system=concept.get('system', 'http://snomed.info/sct'),
                                inactive=concept.get('inactive', False),
                                parent_code=snomed_code
                            ))
                
                all_children.extend(batch_children)
                
                # Check if done
                if len(batch_children) < self.config.batch_size:
                    break
                
                if total_count > 0 and len(all_children) >= total_count:
                    break
                
                # Safety limit
                if len(all_children) >= self.config.max_expansion_results:
                    logger.warning(f"Expansion limit reached for {snomed_code}")
                    break
                
                offset += self.config.batch_size
            
            return ExpansionResult(
                source_code=snomed_code,
                source_display=source_display,
                children=all_children,
                total_count=total_count if total_count > 0 else len(all_children),
                expansion_timestamp=datetime.now(),
                error=None
            )
            
        except TerminologyServerError:
            raise
        except Exception as e:
            error = TerminologyServerError(
                f"Unexpected error during concept expansion: {str(e)}",
                error_type="server_error",
                user_guidance="An unexpected error occurred during expansion. Please try again."
            )
            self.error_handler.handle_error(error)
            
            return ExpansionResult(
                source_code=snomed_code,
                source_display=snomed_code,
                children=[],
                total_count=0,
                expansion_timestamp=datetime.now(),
                error=error.get_user_friendly_message()
            )
    
    def _lookup_concept_details(self, snomed_code: str) -> Tuple[Optional[Dict], Optional[TerminologyServerError]]:
        """Look up concept details for display name"""
        params = {
            'system': 'http://snomed.info/sct',
            'code': snomed_code,
            '_format': 'json'
        }
        
        return self._make_request("CodeSystem/$lookup", params)
    
    def _expand_concept_batch(self, snomed_code: str, include_inactive: bool, 
                            offset: int, batch_size: int) -> Tuple[Optional[Dict], Optional[TerminologyServerError]]:
        """Expand a batch of concepts"""
        ecl_expression = f"< {snomed_code}"
        
        params = {
            'url': f'http://snomed.info/sct?fhir_vs=ecl/{quote(ecl_expression)}',
            '_format': 'json',
            'count': batch_size,
            'offset': offset
        }
        
        if not include_inactive:
            params['activeOnly'] = 'true'
        
        return self._make_request("ValueSet/$expand", params)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection with enhanced error reporting"""
        try:
            response_data, error = self._make_request("metadata", {'_format': 'json'})
            
            if error:
                return False, error.get_user_friendly_message()
            
            if response_data and response_data.get('resourceType') == 'CapabilityStatement':
                return True, "Successfully connected to NHS Terminology Server"
            
            return False, "Connected but received unexpected response format"
            
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def get_statistics(self) -> Dict[str, any]:
        """Get client performance statistics"""
        rate_stats = self.rate_limiter.get_stats()
        
        return {
            'rate_limiter': rate_stats,
            'token_manager': {
                'token_valid': self.token_manager._is_token_valid(),
                'token_expires': self.token_manager.token_expires.isoformat() if self.token_manager.token_expires else None
            },
            'config': {
                'request_timeout': self.config.request_timeout,
                'max_expansion_results': self.config.max_expansion_results,
                'batch_size': self.config.batch_size,
                'debug_mode': self.config.debug_mode
            }
        }


def create_terminology_client(client_id: str, client_secret: str, debug_mode: bool = False) -> NHSTerminologyServerClient:
    """Create an NHS Terminology Server client"""
    credentials = CredentialConfig(
        client_id=client_id,
        client_secret=client_secret
    )
    
    config = ClientConfig(
        debug_mode=debug_mode
    )
    
    return NHSTerminologyServerClient(credentials, config)


class NHSTerminologyClient(NHSTerminologyServerClient):
    """NHS Terminology Server client with enhanced reliability features"""
    
    def __init__(self):
        # Load credentials from streamlit secrets
        try:
            import streamlit as st
            client_id = st.secrets["NHSTSERVER_ID"]
            client_secret = st.secrets["NHSTSERVER_TOKEN"]
            
            credentials = CredentialConfig(
                client_id=client_id,
                client_secret=client_secret
            )
            config = ClientConfig()
            
            super().__init__(credentials, config)
            
        except Exception as e:
            # Fallback for testing or non-Streamlit environments
            credentials = CredentialConfig(
                client_id="",
                client_secret=""
            )
            config = ClientConfig()
            super().__init__(credentials, config)
    
    # Method compatibility  
    def _expand_concept_uncached(self, snomed_code: str, include_inactive: bool = False) -> ExpansionResult:
        """Uncached expansion method"""
        return self.expand_concept(snomed_code, include_inactive)
    
    def _lookup_concept_uncached(self, snomed_code: str) -> Optional[Dict]:
        """Uncached lookup method"""
        result, error = self._lookup_concept_details(snomed_code)
        return result
    
    def lookup_concept(self, snomed_code: str) -> Optional[Dict]:
        """Look up concept details"""
        result, error = self._lookup_concept_details(snomed_code)
        return result
    
    def batch_expand_concepts(self, snomed_codes: List[str], include_inactive: bool = False) -> Dict[str, ExpansionResult]:
        """Expand multiple concepts in batch"""
        results = {}
        for code in snomed_codes:
            results[code] = self.expand_concept(code, include_inactive)
        return results


# Singleton instance
_terminology_client = None

def get_terminology_client() -> NHSTerminologyClient:
    """Get or create the terminology client singleton"""
    global _terminology_client
    if _terminology_client is None:
        _terminology_client = NHSTerminologyClient()
    return _terminology_client