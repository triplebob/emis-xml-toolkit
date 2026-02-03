"""
GitHub Lookup Table Loader

Handles downloading encrypted parquet lookup tables from GitHub.
Returns encrypted bytes for on-demand filtered loading.
"""

import requests
import json
import io
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import pyarrow.parquet as pq

from .lookup_cache import _decrypt_bytes


class GitHubLookupLoader:
    """
    Manages downloading encrypted lookup tables from GitHub.

    Downloads the encrypted parquet file and version info.
    Actual decryption and filtering happens on-demand when processing XML.
    """

    def __init__(self, token: str, lookup_url: str, expiry_date: str):
        """
        Initialise the GitHub loader.

        Args:
            token: GitHub personal access token
            lookup_url: URL to the encrypted parquet file (.enc)
            expiry_date: Token expiry date (YYYY-MM-DD)
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
        """Check if the GitHub token is valid."""
        try:
            response = requests.get("https://api.github.com/user", headers=self.headers, timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            try:
                obfuscated_headers = self._get_obfuscated_headers()
                response = requests.get("https://api.github.com/user", headers=obfuscated_headers, timeout=10)
                return response.status_code == 200
            except requests.RequestException:
                return False

    def days_until_expiry(self) -> int:
        """Calculate days until token expiry."""
        return (self.expiry_date - datetime.now()).days

    def get_expiry_status(self) -> str:
        """Get token expiry status message."""
        days = self.days_until_expiry()
        if days < 0:
            return f"Token expired {abs(days)} day(s) ago on {self.expiry_date.date()}"
        elif days == 0:
            return "Token expires TODAY!"
        elif days < 7:
            return f"Token expires in {days} day(s) on {self.expiry_date.date()}"
        elif days < 30:
            return f"Token expires in {days} days on {self.expiry_date.date()}"
        else:
            return f"Token valid until {self.expiry_date.date()} ({days} days remaining)"

    def get_token_health_status(self) -> Tuple[bool, str]:
        """Get comprehensive token health status."""
        days = self.days_until_expiry()
        if days < 0:
            return False, f"Token expired {abs(days)} day(s) ago - please renew"

        if not self.is_token_valid():
            return False, "Token invalid - please check token permissions"

        if days < 7:
            return True, f"Token valid but expires soon ({days} days) - consider renewal"
        return True, f"Token healthy - valid for {days} more days"

    def _get_obfuscated_headers(self) -> Dict[str, str]:
        """Get browser-like headers for VPN/firewall bypass."""
        return {
            **self.headers,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

    def _convert_to_api_url(self, url: str) -> str:
        """Convert raw GitHub URL to API URL."""
        if 'raw/refs/heads/main' in url:
            # Extract path after 'main/'
            main_idx = url.index('raw/refs/heads/main/') + len('raw/refs/heads/main/')
            file_path = url[main_idx:]

            parts = url.split('/')
            user = parts[3]
            repo = parts[4]

            return f"https://api.github.com/repos/{user}/{repo}/contents/{file_path}"
        return url

    def _download_file(self, url: str) -> bytes:
        """Download file from GitHub, handling API responses."""
        api_url = self._convert_to_api_url(url)

        response = None
        last_error = None

        try:
            response = requests.get(api_url, headers=self.headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            last_error = e
            try:
                response = requests.get(api_url, headers=self._get_obfuscated_headers(), timeout=30)
                response.raise_for_status()
            except requests.RequestException:
                raise last_error

        content_type = response.headers.get('content-type', '')

        if 'application/vnd.github.v3.raw' in content_type:
            return response.content
        elif 'application/json' in content_type:
            import base64
            data = response.json()
            if 'content' not in data:
                raise Exception(f"Invalid GitHub API response - no content field")
            return base64.b64decode(data['content'])
        else:
            # Try as raw content
            return response.content

    def load_encrypted_parquet(self) -> Tuple[bytes, str, str, Dict[str, Any]]:
        """
        Download the encrypted parquet file from GitHub.

        Returns:
            Tuple of (encrypted_bytes, emis_guid_col, snomed_code_col, version_info)

        Raises:
            Exception: If download fails
        """
        is_healthy, status = self.get_token_health_status()
        if not is_healthy and self.days_until_expiry() < 0:
            raise Exception(f"Cannot load lookup table: {status}")

        try:
            # Download encrypted parquet
            encrypted_bytes = self._download_file(self.lookup_url)

            # Validate by checking we can read metadata (requires decryption)
            try:
                parquet_bytes = _decrypt_bytes(encrypted_bytes)
                pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
                columns = [pf.schema_arrow.field(i).name for i in range(len(pf.schema_arrow))]

                # Determine column names
                emis_guid_col = self._find_column_name(columns, ['EMIS_GUID', 'CodeId', 'emis_guid'])
                snomed_code_col = self._find_column_name(columns, ['SNOMED_Code', 'ConceptId', 'snomed_code'])

                if not emis_guid_col or not snomed_code_col:
                    raise Exception(f"Required columns not found. Available: {columns}")

            except ValueError as e:
                raise Exception(f"Failed to decrypt parquet: {str(e)}")

            # Load version info
            version_info = self._load_version_info()

            return encrypted_bytes, emis_guid_col, snomed_code_col, version_info

        except requests.exceptions.Timeout:
            raise Exception("Request timed out while downloading lookup table")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection error while accessing GitHub")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("Authentication failed - check GitHub token")
            elif e.response.status_code == 403:
                raise Exception("Access forbidden - check token permissions")
            elif e.response.status_code == 404:
                raise Exception("Lookup file not found on GitHub")
            raise Exception(f"GitHub API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to load lookup table: {str(e)}")

    def _find_column_name(self, columns: list, candidates: list) -> Optional[str]:
        """Find first matching column name from candidates."""
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    def _load_version_info(self) -> Dict[str, Any]:
        """Load version info JSON from GitHub."""
        version_info = {}
        try:
            # Derive version URL from lookup URL (same directory as .enc file)
            version_url = self.lookup_url.rsplit('/', 1)[0] + '/lookup-version.json'
            version_api_url = self._convert_to_api_url(version_url)

            response = requests.get(version_api_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    data = response.json()
                    if isinstance(data, dict) and 'content' in data:
                        import base64
                        version_content = base64.b64decode(data['content']).decode('utf-8')
                        version_info = json.loads(version_content)
                    else:
                        version_info = data
                else:
                    version_info = json.loads(response.text)
        except Exception:
            pass

        return version_info

    def get_lookup_stats(self) -> Dict[str, Any]:
        """Get lookup table statistics without downloading."""
        return {
            'url': self.lookup_url,
            'token_status': self.get_expiry_status(),
            'format': 'encrypted_parquet',
        }
