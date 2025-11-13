"""
GitHub Lookup Table Loader with Token Management
Handles authentication, token validation, and secure loading of lookup tables.
"""

import requests
import pandas as pd
import io
import json
from datetime import datetime
from typing import Optional, Tuple


class GitHubLookupLoader:
    """
    Manages GitHub authentication and secure loading of lookup tables from private repositories.
    
    Features:
    - Token validation and expiry tracking
    - Secure API requests with proper headers
    - Automatic format detection (CSV/Parquet)
    - Error handling and user-friendly status messages
    """
    
    def __init__(self, token: str, lookup_url: str, expiry_date: str):
        """
        Initialize the GitHub loader with authentication details.
        
        Args:
            token (str): GitHub personal access token
            lookup_url (str): Direct URL to the lookup table file
            expiry_date (str): Token expiry date in YYYY-MM-DD format
        """
        self.token = token
        self.lookup_url = lookup_url
        try:
            self.expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid expiry_date format. Expected YYYY-MM-DD, got: {expiry_date}")
        
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3.raw"
        }
    
    def is_token_valid(self) -> bool:
        """
        Check if the GitHub token is valid by testing API access.
        
        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            # Primary attempt
            response = requests.get("https://api.github.com/user", headers=self.headers, timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            # Fallback with obfuscated headers for VPN bypass
            try:
                obfuscated_headers = {
                    **self.headers,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive"
                }
                response = requests.get("https://api.github.com/user", headers=obfuscated_headers, timeout=10)
                return response.status_code == 200
            except requests.RequestException:
                return False
    
    def days_until_expiry(self) -> int:
        """
        Calculate days until token expiry.
        
        Returns:
            int: Number of days until expiry (negative if expired)
        """
        return (self.expiry_date - datetime.now()).days
    
    def get_expiry_status(self) -> str:
        """
        Get token expiry status.
        
        Returns:
            str: Status message with indicator
        """
        days = self.days_until_expiry()
        if days < 0:
            return f"❌ Token expired {abs(days)} day(s) ago on {self.expiry_date.date()}"
        elif days == 0:
            return "⚠️ Token expires TODAY!"
        elif days < 7:
            return f"⚠️ Token expires in {days} day(s) on {self.expiry_date.date()}"
        elif days < 30:
            return f"🔶 Token expires in {days} days on {self.expiry_date.date()}"
        else:
            return f"✅ Token valid until {self.expiry_date.date()} ({days} days remaining)"
    
    def get_token_health_status(self) -> Tuple[bool, str]:
        """
        Get comprehensive token health status.
        
        Returns:
            Tuple[bool, str]: (is_healthy, status_message)
        """
        # Check expiry first
        days = self.days_until_expiry()
        if days < 0:
            return False, f"❌ Token expired {abs(days)} day(s) ago - please renew"
        
        # Check API validity
        if not self.is_token_valid():
            return False, "❌ Token invalid - please check token permissions"
        
        # Return appropriate status
        if days < 7:
            return True, f"⚠️ Token valid but expires soon ({days} days) - consider renewal"
        else:
            return True, f"✅ Token healthy - valid for {days} more days"
    
    def _detect_file_format(self, url: str) -> str:
        """
        Detect file format from URL.
        
        Args:
            url (str): File URL
            
        Returns:
            str: 'parquet' or 'csv'
        """
        if url.lower().endswith('.parquet'):
            return 'parquet'
        else:
            return 'csv'
    
    def load_lookup_table(self) -> Tuple[pd.DataFrame, str, str, dict]:
        """
        Load the lookup table from GitHub with automatic format detection.
        Also loads version information if available.
        
        Returns:
            Tuple[pd.DataFrame, str, str, dict]: (dataframe, emis_guid_column, snomed_code_column, version_info)
            
        Raises:
            Exception: If loading fails for any reason
        """
        # Check token health before attempting download
        is_healthy, status = self.get_token_health_status()
        if not is_healthy and self.days_until_expiry() < 0:
            raise Exception(f"Cannot load lookup table: {status}")
        
        try:
            # Use GitHub API for private repository access
            # Convert raw URL to API URL if needed
            api_url = self.lookup_url
            if 'raw/refs/heads/main' in self.lookup_url:
                # Convert: github.com/user/repo/raw/refs/heads/main/file.ext
                # To: api.github.com/repos/user/repo/contents/file.ext
                parts = self.lookup_url.split('/')
                user = parts[3]
                repo = parts[4]
                filename = parts[-1]
                api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{filename}"
            
            # Try primary request first, then fallback with obfuscation for VPN/firewall bypass
            response = None
            last_error = None
            
            try:
                # Primary attempt with original headers
                response = requests.get(api_url, headers=self.headers, timeout=30)
                response.raise_for_status()
            except requests.RequestException as e:
                last_error = e
                
                # Fallback: Try with browser-like headers for VPN bypass
                try:
                    obfuscated_headers = {
                        **self.headers,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none"
                    }
                    
                    response = requests.get(api_url, headers=obfuscated_headers, timeout=30)
                    response.raise_for_status()
                except requests.RequestException:
                    # If both attempts fail, raise the original error
                    raise last_error
            
            # Check content type to determine how to handle the response
            content_type = response.headers.get('content-type', '')
            
            if 'application/vnd.github.v3.raw' in content_type:
                # GitHub returned raw file content directly
                file_content = response.content
                file_format = self._detect_file_format(api_url)
                
                if file_format == 'parquet':
                    # Load parquet from bytes
                    lookup_df = pd.read_parquet(io.BytesIO(file_content))
                else:
                    # Load CSV from text
                    lookup_df = pd.read_csv(io.StringIO(response.text))
                    
            elif 'application/json' in content_type:
                # GitHub API returned JSON with base64 encoded content
                import base64
                
                try:
                    data = response.json()
                except ValueError as e:
                    response_preview = response.text[:200] if response.text else "Empty response"
                    raise Exception(f"Invalid JSON response from GitHub API. Response preview: {response_preview}")
                
                if 'content' not in data:
                    raise Exception(f"Invalid GitHub API response - no content field. Response keys: {list(data.keys())}")
                
                # Decode base64 content
                file_content = base64.b64decode(data['content'])
                file_format = self._detect_file_format(data.get('name', api_url))
                
                if file_format == 'parquet':
                    # Load parquet from bytes
                    lookup_df = pd.read_parquet(io.BytesIO(file_content))
                else:
                    # Load CSV from decoded text
                    lookup_df = pd.read_csv(io.StringIO(file_content.decode('utf-8')))
            else:
                raise Exception(f"Unexpected content type from GitHub API: {content_type}")
            
            # Determine column names
            emis_guid_col = self._find_column(lookup_df, ['EMIS_GUID', 'CodeId', 'Code_Id', 'emis_guid'])
            snomed_code_col = self._find_column(lookup_df, ['SNOMED_Code', 'ConceptId', 'Concept_Id', 'snomed_code'])
            
            if not emis_guid_col or not snomed_code_col:
                available_cols = list(lookup_df.columns)
                raise Exception(f"Required columns not found. Available columns: {available_cols}")
            
            # Try to load version information
            version_info = {}
            try:
                # For now, use the known working pattern
                # TODO: Make this configurable when more lookup files are added
                version_url = self.lookup_url.replace('emis-complete-lookup.parquet', 'lookup-version.json')
                if 'raw/refs/heads/main' in version_url:
                    # Convert to API URL
                    parts = version_url.split('/')
                    user = parts[3]
                    repo = parts[4]
                    filename = parts[-1]
                    version_api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{filename}"
                else:
                    version_api_url = version_url
                    
                version_response = requests.get(version_api_url, headers=self.headers, timeout=10)
                if version_response.status_code == 200:
                    content_type = version_response.headers.get('content-type', '')
                    try:
                        if 'application/json' in content_type:
                            data = version_response.json()
                            if isinstance(data, dict) and 'content' in data:
                                import base64
                                version_content = base64.b64decode(data['content']).decode('utf-8')
                                version_info = json.loads(version_content)
                            else:
                                # Direct JSON content
                                version_info = data
                        elif 'application/vnd.github.v3.raw' in content_type:
                            # Try to parse raw JSON
                            version_info = version_response.json()
                        else:
                            # Fallback: try to parse as JSON
                            version_info = json.loads(version_response.text)
                    except Exception:
                        pass
            except:
                # Version info is optional, continue without it
                pass
            
            return lookup_df, emis_guid_col, snomed_code_col, version_info
            
        except requests.exceptions.Timeout as e:
            raise Exception(f"Request timed out while downloading lookup table. Please check your connection and try again: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"Connection error while accessing GitHub. Please check your network connection: {str(e)}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed. Please check your GitHub token permissions and ensure it has access to the repository.")
            elif e.response.status_code == 403:
                if 'rate limit' in str(e).lower():
                    raise Exception("GitHub API rate limit exceeded. Please wait and try again, or check your token's rate limit status.")
                else:
                    raise Exception("Access forbidden. Please verify your GitHub token has the correct repository permissions.")
            elif e.response.status_code == 404:
                raise Exception("Lookup table file not found. Please verify the repository URL and file path are correct.")
            else:
                raise Exception(f"GitHub API error (HTTP {e.response.status_code}): {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error while downloading lookup table: {str(e)}")
        except pd.errors.ParserError as e:
            raise Exception(f"Failed to parse lookup table. The file may be corrupted or in an unexpected format: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from GitHub API. The response may be malformed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error loading lookup table: {str(e)}")
    
    def _find_column(self, df: pd.DataFrame, possible_names: list) -> Optional[str]:
        """
        Find the first matching column name from a list of possibilities.
        
        Args:
            df (pd.DataFrame): DataFrame to search
            possible_names (list): List of possible column names
            
        Returns:
            Optional[str]: First matching column name, or None if not found
        """
        for col_name in possible_names:
            if col_name in df.columns:
                return col_name
        return None
    
    def get_lookup_stats(self) -> dict:
        """
        Get statistics about the lookup table without fully loading it.
        Useful for displaying info in UI.
        
        Returns:
            dict: Statistics including file format, estimated size, etc.
        """
        file_format = self._detect_file_format(self.lookup_url)
        return {
            'file_format': file_format.upper(),
            'url': self.lookup_url,
            'token_status': self.get_expiry_status(),
            'estimated_load_time': '2-5 seconds' if file_format == 'parquet' else '5-15 seconds'
        }
