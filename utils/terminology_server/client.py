"""
NHS England Terminology Server Client

Simplified client for SNOMED concept expansion using NHS FHIR terminology server.
Features:
- OAuth2 authentication with thread-safe token management
- Automatic token refresh
- Retry logic for failed requests
- Simple rate limiting
"""

import requests
import json
import time
import threading
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ExpandedConcept:
    """Represents an expanded SNOMED concept from the terminology server"""
    code: str
    display: str
    system: str = "http://snomed.info/sct"
    inactive: bool = False


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
class TerminologyServerConfig:
    """Configuration for NHS Terminology Server"""
    client_id: str
    client_secret: str
    base_url: str = "https://ontology.nhs.uk/production1/fhir"
    auth_url: str = "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"
    request_timeout: int = 30
    max_concurrent: int = 20
    max_retries: int = 3
    max_expansion_results: int = 50000
    expansion_page_size: int = 1000


class TokenManager:
    """Thread-safe OAuth2 token management"""

    def __init__(self, config: TerminologyServerConfig):
        self.config = config
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
        """Check if current token is still valid (with 5-minute buffer)"""
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
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret
            }

            response = requests.post(
                self.config.auth_url,
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

            else:
                logger.error(f"Authentication failed with status {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None

        finally:
            self._authenticating = False

    def invalidate_token(self):
        """Invalidate the current token to force re-authentication"""
        with self._lock:
            self.access_token = None
            self.token_expires = None


class NHSTerminologyClient:
    """
    NHS Terminology Server client for SNOMED concept expansion
    """

    def __init__(self, config: TerminologyServerConfig):
        self.config = config
        self.token_manager = TokenManager(config)
        self._request_times = []
        self._lock = threading.RLock()

        logger.info("Initialised NHS Terminology Server client")

    def _rate_limit(self):
        """Simple rate limiting: max 10 requests per second"""
        with self._lock:
            now = time.time()
            # Remove requests older than 1 second
            self._request_times = [t for t in self._request_times if now - t < 1.0]

            # If we're at the limit, wait
            if len(self._request_times) >= 10:
                sleep_time = 1.0 - (now - self._request_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._request_times = []

            self._request_times.append(now)

    def _make_request(
        self,
        endpoint: str,
        params: Dict = None,
        retry_count: int = 0
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Make authenticated request with retry logic

        Returns:
            (response_json, error_message)
        """
        # Apply rate limiting
        self._rate_limit()

        # Get valid authentication token
        token = self.token_manager.get_valid_token()
        if not token:
            return None, "Failed to obtain authentication token"

        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json',
            'User-Agent': 'ClinXML-EMIS-Converter/1.0'
        }

        url = f"{self.config.base_url}/{endpoint}"

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.config.request_timeout
            )

            # Handle response status codes
            if response.status_code == 200:
                try:
                    return response.json(), None
                except json.JSONDecodeError:
                    return None, "Invalid JSON response from server"

            elif response.status_code == 401:
                # Token expired - invalidate and retry
                self.token_manager.invalidate_token()

                if retry_count < self.config.max_retries:
                    logger.info(f"Token expired, retrying request (attempt {retry_count + 1})")
                    time.sleep(0.5 * (retry_count + 1))  # Exponential backoff
                    return self._make_request(endpoint, params, retry_count + 1)

                return None, "Authentication failed after retries"

            elif response.status_code == 404:
                return None, f"Resource not found: {endpoint}"

            elif response.status_code == 422:
                # Unprocessable entity - invalid parameters
                error_detail = response.text[:200] if response.text else "Invalid request"
                return None, f"Invalid request parameters: {error_detail}"

            elif response.status_code == 429:
                # Rate limited
                if retry_count < self.config.max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1)

                return None, "Rate limit exceeded"

            elif response.status_code >= 500:
                # Server error - retry
                if retry_count < self.config.max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1)

                return None, f"Server error: {response.status_code}"

            else:
                return None, f"Unexpected response status: {response.status_code}"

        except requests.exceptions.Timeout:
            if retry_count < self.config.max_retries:
                logger.warning(f"Request timeout, retrying (attempt {retry_count + 1})")
                time.sleep(1)
                return self._make_request(endpoint, params, retry_count + 1)
            return None, "Request timeout"

        except requests.exceptions.ConnectionError:
            return None, "Connection error - cannot reach NHS Terminology Server"

        except Exception as e:
            logger.error(f"Unexpected error in request: {str(e)}")
            return None, f"Unexpected error: {str(e)}"

    def expand_concept(
        self,
        code: str,
        include_inactive: bool = False
    ) -> ExpansionResult:
        """
        Expand a SNOMED concept to retrieve all child concepts

        Args:
            code: SNOMED CT concept code
            include_inactive: Include inactive/deprecated concepts

        Returns:
            ExpansionResult with children or error
        """
        try:
            source_display = "Unknown"
            lookup_display, lookup_error = self.lookup_concept(code)
            if lookup_display and not lookup_error:
                source_display = lookup_display

            all_children: List[ExpandedConcept] = []
            offset = 0
            total_count = 0
            page_size = self.config.expansion_page_size
            ecl_expression = f"< {code}"

            while True:
                params = {
                    'url': f'http://snomed.info/sct?fhir_vs=ecl/{quote(ecl_expression)}',
                    'count': page_size,
                    'offset': offset,
                    'includeDesignations': 'false',
                    'activeOnly': 'false' if include_inactive else 'true'
                }

                response, error = self._make_request('ValueSet/$expand', params)

                if error:
                    if offset == 0:
                        return ExpansionResult(
                            source_code=code,
                            source_display=source_display,
                            children=[],
                            total_count=0,
                            expansion_timestamp=datetime.now(),
                            error=error
                        )
                    break

                expansion = response.get('expansion', {})
                contains = expansion.get('contains', [])
                if offset == 0:
                    total_count = expansion.get('total', 0)

                for concept in contains:
                    all_children.append(ExpandedConcept(
                        code=concept.get('code', ''),
                        display=concept.get('display', ''),
                        system=concept.get('system', 'http://snomed.info/sct'),
                        inactive=concept.get('inactive', False)
                    ))

                if len(contains) < page_size:
                    break

                if total_count and len(all_children) >= total_count:
                    break

                if len(all_children) >= self.config.max_expansion_results:
                    break

                offset += page_size

            return ExpansionResult(
                source_code=code,
                source_display=source_display,
                children=all_children,
                total_count=total_count if total_count > 0 else len(all_children),
                expansion_timestamp=datetime.now(),
                error=None
            )

        except Exception as e:
            logger.error(f"Error expanding concept {code}: {str(e)}")
            return ExpansionResult(
                source_code=code,
                source_display="Unknown",
                children=[],
                total_count=0,
                expansion_timestamp=datetime.now(),
                error=f"Expansion failed: {str(e)}"
            )

    def lookup_concept(self, code: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Lookup a SNOMED concept to get its display name

        Args:
            code: SNOMED CT concept code

        Returns:
            (display_name, error_message)
        """
        params = {
            'system': 'http://snomed.info/sct',
            'code': code
        }

        response, error = self._make_request('CodeSystem/$lookup', params)

        if error:
            return None, error

        # Parse lookup response
        if 'parameter' in response:
            for param in response['parameter']:
                if param.get('name') == 'display':
                    return param.get('valueString'), None

        return None, "Display name not found in response"

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to NHS Terminology Server

        Returns:
            (success, message)
        """
        try:
            token = self.token_manager.get_valid_token()
            if not token:
                return False, "Failed to authenticate"

            # Try a simple lookup
            display, error = self.lookup_concept('73211009')  # Diabetes mellitus

            if error:
                return False, f"Connection test failed: {error}"

            return True, f"Connection successful. Test lookup returned: {display}"

        except Exception as e:
            return False, f"Connection test error: {str(e)}"
