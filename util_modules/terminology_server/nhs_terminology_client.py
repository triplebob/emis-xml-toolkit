"""
NHS England Terminology Server Client

This module provides integration with the NHS England Terminology Server
for expanding SNOMED CT codes with includechildren=True functionality.

The client uses system-to-system authentication and implements FHIR R4
operations for concept expansion and hierarchy queries.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import quote
import streamlit as st
from dataclasses import dataclass
from datetime import datetime, timedelta


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


class NHSTerminologyClient:
    """Client for NHS England Terminology Server with FHIR R4 API"""
    
    def __init__(self):
        self.base_url = "https://ontology.nhs.uk/production1/fhir"
        self.auth_url = "https://ontology.nhs.uk/authorisation/auth/realms/nhs-digital-terminology/protocol/openid-connect/token"
        self.client_id = None
        self.client_secret = None
        self.access_token = None
        self.token_expires = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Load credentials from Streamlit secrets"""
        try:
            self.client_id = st.secrets["NHSTSERVER_ID"]
            self.client_secret = st.secrets["NHSTSERVER_TOKEN"]
        except KeyError as e:
            st.error(f"Missing NHS Terminology Server credentials: {e}")
            raise ValueError(f"Missing credential: {e}")
    
    def _is_token_valid(self) -> bool:
        """Check if current access token is still valid"""
        if not self.access_token or not self.token_expires:
            return False
        # Add 5 minute buffer before expiry
        return datetime.now() < (self.token_expires - timedelta(minutes=5))
    
    def _authenticate(self) -> bool:
        """Authenticate with NHS Terminology Server using system-to-system credentials"""
        try:
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            response = requests.post(
                self.auth_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 1800)  # Default 30 minutes
                self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                return True
            else:
                st.error(f"Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        if not self._is_token_valid():
            return self._authenticate()
        return True
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Tuple[Optional[Dict], Optional[str]]:
        """Make authenticated request to terminology server"""
        if not self._ensure_authenticated():
            return None, "Authentication failed"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
        
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 401:
                # Token might have expired, try re-authenticating once
                if self._authenticate():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                    if response.status_code == 200:
                        return response.json(), None
            
            # Don't show error in UI, return error details for proper handling
            if response.status_code == 404:
                return None, "Code does not exist in terminology server"
            elif response.status_code >= 500:
                return None, "Terminology server error"
            else:
                return None, f"API request failed: {response.status_code}"
            
        except Exception as e:
            return None, f"Connection error: {str(e)}"
    
    def _expand_concept_uncached(self, snomed_code: str, include_inactive: bool = False) -> ExpansionResult:
        """Uncached version for worker threads with automatic pagination"""
        try:
            # First, look up the concept to get its display name
            source_display = snomed_code
            try:
                lookup_result = self._lookup_concept_uncached(snomed_code)
                if lookup_result and 'parameter' in lookup_result:
                    for param in lookup_result.get('parameter', []):
                        if param.get('name') == 'display':
                            source_display = param.get('valueString', snomed_code)
                            break
            except Exception:
                # If lookup fails, continue with the code as display
                pass
            
            # Use the correct FHIR ValueSet $expand operation with ECL
            # ECL: < means "all descendants of" (children, grandchildren, etc.)
            ecl_expression = f"< {snomed_code}"
            
            # Fetch all results using pagination
            all_children = []
            offset = 0
            batch_size = 1000
            total_count = 0
            
            while True:
                # Create request parameters for this batch
                params = {
                    'url': f'http://snomed.info/sct?fhir_vs=ecl/{quote(ecl_expression)}',
                    '_format': 'json',
                    'count': batch_size,
                    'offset': offset
                }
                
                if not include_inactive:
                    params['activeOnly'] = 'true'
                
                # Make the ValueSet $expand request for this batch
                response_data, error_message = self._make_request(
                    "ValueSet/$expand",
                    params=params
                )
                
                if not response_data:
                    # If first batch fails, return error
                    if offset == 0:
                        return ExpansionResult(
                            source_code=snomed_code,
                            source_display="Unknown",
                            children=[],
                            total_count=0,
                            expansion_timestamp=datetime.now(),
                            error=error_message or "Unknown error"
                        )
                    else:
                        # If later batch fails, break and return what we have
                        break
                
                # Parse this batch of results
                batch_children = []
                
                if 'expansion' in response_data:
                    expansion = response_data['expansion']
                    # Get total count from first batch
                    if offset == 0:
                        total_count = expansion.get('total', 0)
                    
                    if 'contains' in expansion:
                        for concept in expansion['contains']:
                            # All concepts in the expansion are children (ECL < excludes the parent)
                            batch_children.append(ExpandedConcept(
                                code=concept.get('code', ''),
                                display=concept.get('display', ''),
                                system=concept.get('system', 'http://snomed.info/sct'),
                                inactive=concept.get('inactive', False),
                                parent_code=snomed_code
                            ))
                
                # Add this batch to our collection
                all_children.extend(batch_children)
                
                # Check if we're done
                if len(batch_children) < batch_size:
                    # Received fewer results than requested, we're at the end
                    break
                
                if total_count > 0 and len(all_children) >= total_count:
                    # We have all the results according to total_count
                    break
                
                # Prepare for next batch
                offset += batch_size
                
                # Safety limit: don't fetch more than 50,000 results in one expansion
                # This prevents runaway requests on very large concept hierarchies
                if len(all_children) >= 50000:
                    break
            
            return ExpansionResult(
                source_code=snomed_code,
                source_display=source_display,
                children=all_children,
                total_count=total_count if total_count > 0 else len(all_children),
                expansion_timestamp=datetime.now(),
                error=None
            )
            
        except Exception as e:
            return ExpansionResult(
                source_code=snomed_code,
                source_display="Unknown",
                children=[],
                total_count=0,
                expansion_timestamp=datetime.now(),
                error=str(e)
            )

    # @st.cache_data(ttl=3600, max_entries=2000)  # Disabled - _self conflicts with worker threads
    def expand_concept(self, snomed_code: str, include_inactive: bool = False) -> ExpansionResult:
        """
        Expand a SNOMED concept to get all child concepts using $expand operation with automatic pagination
        
        Args:
            snomed_code: The SNOMED CT code to expand
            include_inactive: Whether to include inactive concepts
            
        Returns:
            ExpansionResult with child concepts or error information
        """
        # Delegate to the uncached version which now has pagination
        return self._expand_concept_uncached(snomed_code, include_inactive)
    
    def _lookup_concept_uncached(self, snomed_code: str) -> Optional[Dict]:
        """Uncached version for worker threads - identical logic to lookup_concept"""
        params = {
            'system': 'http://snomed.info/sct',
            'code': snomed_code,
            '_format': 'json'
        }
        
        result, error = self._make_request("CodeSystem/$lookup", params)
        return result

    # @st.cache_data(ttl=3600, max_entries=1000)  # Temporarily disabled to debug _self issue
    def lookup_concept(self, snomed_code: str) -> Optional[Dict]:
        """
        Look up a single SNOMED concept for details
        
        Args:
            snomed_code: The SNOMED CT code to look up
            
        Returns:
            Concept details or None if not found
        """
        params = {
            'system': 'http://snomed.info/sct',
            'code': snomed_code,
            '_format': 'json'
        }
        
        result, error = self._make_request("CodeSystem/$lookup", params)
        return result
    
    def batch_expand_concepts(self, snomed_codes: List[str], include_inactive: bool = False) -> Dict[str, ExpansionResult]:
        """
        Expand multiple SNOMED concepts in batch
        
        Args:
            snomed_codes: List of SNOMED CT codes to expand
            include_inactive: Whether to include inactive concepts
            
        Returns:
            Dictionary mapping codes to their expansion results
        """
        results = {}
        
        # Progress tracking for batch operations
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            for i, code in enumerate(snomed_codes):
                status_text.text(f"Expanding {code} ({i+1}/{len(snomed_codes)})")
                
                result = self.expand_concept(code, include_inactive)
                results[code] = result
                
                # Update progress
                progress = (i + 1) / len(snomed_codes)
                progress_bar.progress(progress)
                
                # Small delay to avoid overwhelming the server
                time.sleep(0.1)
                
        finally:
            progress_bar.empty()
            status_text.empty()
        
        return results
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to NHS Terminology Server
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if not self._ensure_authenticated():
                return False, "Authentication failed"
            
            # Test with a simple metadata request
            response_data, error_message = self._make_request("metadata", {'_format': 'json'})
            
            if response_data and response_data.get('resourceType') == 'CapabilityStatement':
                return True, "Successfully connected to NHS Terminology Server"
            else:
                return False, error_message or "Connected but received unexpected response"
                
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"


# Singleton instance for the application
_terminology_client = None

def get_terminology_client() -> NHSTerminologyClient:
    """Get or create the terminology client singleton"""
    global _terminology_client
    if _terminology_client is None:
        _terminology_client = NHSTerminologyClient()
    return _terminology_client