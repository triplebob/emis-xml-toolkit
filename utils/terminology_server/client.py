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
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categorises NHS Terminology Server errors for user-friendly messaging"""
    NONE = "none"
    AUTH_FAILURE = "auth_failure"
    INVALID_CODE_FORMAT = "invalid_code_format"
    CODE_NOT_FOUND = "code_not_found"
    NO_MATCHES = "no_matches"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class TerminologyError:
    """Structured error with category and user-friendly message"""
    category: ErrorCategory
    message: str
    suggestion: str = ""
    technical_detail: str = ""

    def __str__(self) -> str:
        return self.message


ERROR_MESSAGES = {
    ErrorCategory.AUTH_FAILURE: TerminologyError(
        category=ErrorCategory.AUTH_FAILURE,
        message="Authentication failed",
        suggestion="Check NHS Terminology Server credentials in secrets configuration"
    ),
    ErrorCategory.INVALID_CODE_FORMAT: TerminologyError(
        category=ErrorCategory.INVALID_CODE_FORMAT,
        message="Invalid SNOMED code format",
        suggestion="SNOMED codes should be numeric (e.g., 73211009)"
    ),
    ErrorCategory.CODE_NOT_FOUND: TerminologyError(
        category=ErrorCategory.CODE_NOT_FOUND,
        message="Code not found in SNOMED CT",
        suggestion="Verify the code exists in the current SNOMED CT release"
    ),
    ErrorCategory.NO_MATCHES: TerminologyError(
        category=ErrorCategory.NO_MATCHES,
        message="No matching concepts found",
        suggestion="The code may be a leaf concept with no children"
    ),
    ErrorCategory.RATE_LIMITED: TerminologyError(
        category=ErrorCategory.RATE_LIMITED,
        message="Rate limit exceeded",
        suggestion="Please wait a moment before trying again"
    ),
    ErrorCategory.SERVER_ERROR: TerminologyError(
        category=ErrorCategory.SERVER_ERROR,
        message="NHS Terminology Server error",
        suggestion="The server may be temporarily unavailable - try again later"
    ),
    ErrorCategory.CONNECTION_ERROR: TerminologyError(
        category=ErrorCategory.CONNECTION_ERROR,
        message="Cannot connect to NHS Terminology Server",
        suggestion="Check your internet connection"
    ),
    ErrorCategory.TIMEOUT: TerminologyError(
        category=ErrorCategory.TIMEOUT,
        message="Request timed out",
        suggestion="The server may be busy - try again"
    ),
}


def _parse_fhir_error(response_text: str) -> Tuple[ErrorCategory, str]:
    """
    Parse FHIR OperationOutcome to extract error details

    Returns:
        (ErrorCategory, detail_message)
    """
    try:
        data = json.loads(response_text)

        if data.get("resourceType") == "OperationOutcome":
            issues = data.get("issue", [])
            for issue in issues:
                diagnostics = issue.get("diagnostics", "").lower()
                details_text = issue.get("details", {}).get("text", "").lower()
                combined = f"{diagnostics} {details_text}"

                # Check for "no matches" patterns
                if any(phrase in combined for phrase in [
                    "no match", "no results", "empty expansion",
                    "valueset contains 0 codes", "0 concepts"
                ]):
                    return ErrorCategory.NO_MATCHES, issue.get("diagnostics", "No matches found")

                # Check for invalid code format
                if any(phrase in combined for phrase in [
                    "invalid code", "invalid snomed", "malformed",
                    "not a valid", "syntax error", "parse error"
                ]):
                    return ErrorCategory.INVALID_CODE_FORMAT, issue.get("diagnostics", "Invalid code format")

                # Check for code not found
                if any(phrase in combined for phrase in [
                    "not found", "unknown code", "concept not found",
                    "does not exist"
                ]):
                    return ErrorCategory.CODE_NOT_FOUND, issue.get("diagnostics", "Code not found")

            # Return first issue diagnostics if no pattern matched
            if issues:
                return ErrorCategory.UNKNOWN, issues[0].get("diagnostics", response_text[:200])

    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    return ErrorCategory.UNKNOWN, response_text[:200] if response_text else "Unknown error"


def _validate_snomed_code(code: str) -> Optional[str]:
    """
    Validate SNOMED code format

    Returns:
        Error message if invalid, None if valid
    """
    if not code or not code.strip():
        return "Code cannot be empty"

    code = code.strip()

    # SNOMED codes should be numeric and typically 6-18 digits
    if not code.isdigit():
        return f"Invalid code format: '{code}' should contain only numbers"

    if len(code) < 6:
        return f"Code '{code}' is too short (SNOMED codes are typically 6-18 digits)"

    if len(code) > 18:
        return f"Code '{code}' is too long (SNOMED codes are typically 6-18 digits)"

    return None


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
            err = ERROR_MESSAGES[ErrorCategory.AUTH_FAILURE]
            return None, f"{err.message}. {err.suggestion}"

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
                err = ERROR_MESSAGES[ErrorCategory.CODE_NOT_FOUND]
                return None, f"{err.message}. {err.suggestion}"

            elif response.status_code == 422:
                # Parse FHIR OperationOutcome for detailed error
                category, detail = _parse_fhir_error(response.text)

                if category == ErrorCategory.NO_MATCHES:
                    err = ERROR_MESSAGES[ErrorCategory.NO_MATCHES]
                    return None, f"{err.message}. {err.suggestion}"
                elif category == ErrorCategory.INVALID_CODE_FORMAT:
                    err = ERROR_MESSAGES[ErrorCategory.INVALID_CODE_FORMAT]
                    return None, f"{err.message}. {err.suggestion}"
                elif category == ErrorCategory.CODE_NOT_FOUND:
                    err = ERROR_MESSAGES[ErrorCategory.CODE_NOT_FOUND]
                    return None, f"{err.message}. {err.suggestion}"
                else:
                    return None, f"Request failed: {detail}"

            elif response.status_code == 429:
                # Rate limited
                if retry_count < self.config.max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1)

                err = ERROR_MESSAGES[ErrorCategory.RATE_LIMITED]
                return None, f"{err.message}. {err.suggestion}"

            elif response.status_code >= 500:
                # Server error - retry
                if retry_count < self.config.max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1)

                err = ERROR_MESSAGES[ErrorCategory.SERVER_ERROR]
                return None, f"{err.message} (HTTP {response.status_code}). {err.suggestion}"

            else:
                return None, f"Unexpected response status: {response.status_code}"

        except requests.exceptions.Timeout:
            if retry_count < self.config.max_retries:
                logger.warning(f"Request timeout, retrying (attempt {retry_count + 1})")
                time.sleep(1)
                return self._make_request(endpoint, params, retry_count + 1)
            err = ERROR_MESSAGES[ErrorCategory.TIMEOUT]
            return None, f"{err.message}. {err.suggestion}"

        except requests.exceptions.ConnectionError:
            err = ERROR_MESSAGES[ErrorCategory.CONNECTION_ERROR]
            return None, f"{err.message}. {err.suggestion}"

        except Exception as e:
            logger.error(f"Unexpected error in request: {str(e)}")
            return None, f"Unexpected error: {str(e)}"

    def expand_concept(
        self,
        code: str,
        include_inactive: bool = False,
        source_display: Optional[str] = None
    ) -> ExpansionResult:
        """
        Expand a SNOMED concept to retrieve all child concepts

        Args:
            code: SNOMED CT concept code
            include_inactive: Include inactive/deprecated concepts
            source_display: Pre-fetched display name (skips redundant lookup if provided)

        Returns:
            ExpansionResult with children or error
        """
        # Validate code format first
        validation_error = _validate_snomed_code(code)
        if validation_error:
            err = ERROR_MESSAGES[ErrorCategory.INVALID_CODE_FORMAT]
            return ExpansionResult(
                source_code=code,
                source_display="Unknown",
                children=[],
                total_count=0,
                expansion_timestamp=datetime.now(),
                error=f"{err.message}: {validation_error}"
            )

        code = code.strip()

        try:
            # Use provided display name or fetch it
            if source_display:
                display = source_display
            else:
                display = "Unknown"
                lookup_display, lookup_error = self.lookup_concept(code)
                if lookup_display and not lookup_error:
                    display = lookup_display
                elif lookup_error and "not found" in lookup_error.lower():
                    # Code doesn't exist - return early with clear error
                    return ExpansionResult(
                        source_code=code,
                        source_display="Unknown",
                        children=[],
                        total_count=0,
                        expansion_timestamp=datetime.now(),
                        error=f"SNOMED code '{code}' not found in NHS Terminology Server"
                    )
            source_display = display

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
        # Validate code format first
        validation_error = _validate_snomed_code(code)
        if validation_error:
            err = ERROR_MESSAGES[ErrorCategory.INVALID_CODE_FORMAT]
            return None, f"{err.message}: {validation_error}"

        params = {
            'system': 'http://snomed.info/sct',
            'code': code.strip()
        }

        response, error = self._make_request('CodeSystem/$lookup', params)

        if error:
            # Make error more specific for lookup failures
            if "not found" in error.lower():
                return None, f"SNOMED code '{code}' not found in NHS Terminology Server"
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
