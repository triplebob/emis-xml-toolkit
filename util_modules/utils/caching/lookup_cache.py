"""
EMIS Lookup Table Cache Management

This module handles building and managing the persistent cache for the EMIS lookup table,
optimizing performance for terminology server integrations and other lookup operations.

Supports both local caching (for development) and GitHub-based caching (for production).
"""

import pandas as pd
import streamlit as st
import pickle
import gzip
import hashlib
import os
import requests
from typing import Dict, Optional, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


def _get_encryption_key() -> Optional[bytes]:
    """Get encryption key from Streamlit secrets"""
    try:
        password = st.secrets["GZIP_TOKEN"]
        # Use a fixed salt for consistency across sessions
        salt = b'emis_cache_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    except KeyError:
        # No encryption token available - cache will be unencrypted
        return None
    except Exception:
        # Other errors - cache will be unencrypted
        return None


def _encrypt_data(data: bytes) -> bytes:
    """Encrypt data using the GZIP_TOKEN"""
    encryption_key = _get_encryption_key()
    if encryption_key is None:
        # No encryption available - return data as-is
        return data
    
    try:
        fernet = Fernet(encryption_key)
        return fernet.encrypt(data)
    except Exception:
        # Encryption failed - return data as-is
        return data


def _decrypt_data(encrypted_data: bytes) -> bytes:
    """Decrypt data using the GZIP_TOKEN"""
    encryption_key = _get_encryption_key()
    if encryption_key is None:
        # No encryption key - assume data is unencrypted
        return encrypted_data
    
    try:
        fernet = Fernet(encryption_key)
        return fernet.decrypt(encrypted_data)
    except Exception:
        # Decryption failed - assume data is unencrypted and return as-is
        return encrypted_data


def _get_lookup_table_hash_from_version_info(version_info: Dict) -> str:
    """Generate hash from lookup version info JSON"""
    if not version_info:
        return "unknown"
    
    # Create hash from standardized version info
    hash_data = (
        f"emis_{version_info.get('emis_version', '')}_"
        f"snomed_{version_info.get('snomed_version', '')}_"
        f"extract_{version_info.get('extract_date', '')}_"
        f"clinical_{version_info.get('total_clinical_codes', '')}_"
        f"medication_{version_info.get('total_medication_codes', '')}"
    )
    return hashlib.md5(hash_data.encode()).hexdigest()[:12]


def _get_lookup_table_hash(lookup_df: pd.DataFrame, version_info: Dict = None) -> str:
    """Generate a hash of the lookup table for cache validation - ONLY uses version_info"""
    if lookup_df is None or lookup_df.empty:
        return "empty"
    
    # REQUIRE version_info - no fallbacks allowed
    if not version_info or len(version_info) == 0:
        raise ValueError(f"version_info is required for cache hashing. The GitHub loader failed to load lookup-version.json. This file should contain version information extracted from the CSV files during parquet generation. Received: {version_info}")
    
    return _get_lookup_table_hash_from_version_info(version_info)


def _get_cache_directory() -> str:
    """Get or create the cache directory"""
    cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _get_github_cache_url(table_hash: str) -> str:
    """Get GitHub URL for the cache file"""
    return f"https://raw.githubusercontent.com/triplebob/emis-xml-toolkit/main/.cache/emis_lookup_{table_hash}.pkl"


def _download_github_cache(table_hash: str) -> Optional[Dict]:
    """
    Download cache from GitHub repository
    
    Args:
        table_hash: Hash of the lookup table
        
    Returns:
        Cache data dict or None if not available
    """
    try:
        cache_url = _get_github_cache_url(table_hash)
        response = requests.get(cache_url, timeout=10)
        
        if response.status_code == 200:
            # Try decryption first, then gzip decompression
            try:
                # Attempt to decrypt the data
                decrypted_data = _decrypt_data(response.content)
                
                # Try gzip decompression first, fallback to uncompressed
                try:
                    cache_data = pickle.loads(gzip.decompress(decrypted_data))
                except (gzip.BadGzipFile, OSError):
                    # Fallback for old uncompressed cache files
                    cache_data = pickle.loads(decrypted_data)
            except Exception:
                # If decryption fails, try without decryption (backward compatibility)
                try:
                    cache_data = pickle.loads(gzip.decompress(response.content))
                except (gzip.BadGzipFile, OSError):
                    cache_data = pickle.loads(response.content)
            
            # Validate cache structure
            if (isinstance(cache_data, dict) and 
                'lookup_mapping' in cache_data and 
                'lookup_records' in cache_data):
                return cache_data
        
    except Exception as e:
        # Silently fail - will fall back to local cache or building
        pass
    
    return None


def _save_local_cache(cache_data: Dict, table_hash: str) -> bool:
    """
    Save cache data to local file system
    
    Args:
        cache_data: Complete cache data dictionary
        table_hash: Hash of the lookup table
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cache_dir = _get_cache_directory()
        cache_file = os.path.join(cache_dir, f"emis_lookup_{table_hash}.pkl")
        
        # Compress first, then encrypt
        compressed_data = gzip.compress(pickle.dumps(cache_data, protocol=pickle.HIGHEST_PROTOCOL))
        encrypted_data = _encrypt_data(compressed_data)
        
        with open(cache_file, 'wb') as f:
            f.write(encrypted_data)
        
        # Clean up old cache files (keep only the latest)
        _cleanup_old_cache_files(cache_dir, table_hash)
        return True
        
    except Exception:
        return False


def _load_local_cache(table_hash: str, snomed_code_col: str, emis_guid_col: str) -> Optional[Dict]:
    """
    Load cache from local file system
    
    Args:
        table_hash: Hash of the lookup table
        snomed_code_col: Expected SNOMED column name
        emis_guid_col: Expected EMIS GUID column name
        
    Returns:
        Cache data dict or None if not available
    """
    try:
        cache_dir = _get_cache_directory()
        cache_file = os.path.join(cache_dir, f"emis_lookup_{table_hash}.pkl")
        
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                encrypted_data = f.read()
                
            # Decrypt first, then decompress
            try:
                decrypted_data = _decrypt_data(encrypted_data)
                cached_data = pickle.loads(gzip.decompress(decrypted_data))
            except Exception:
                # Fallback for old unencrypted cache files
                try:
                    cached_data = pickle.loads(gzip.decompress(encrypted_data))
                except (gzip.BadGzipFile, OSError):
                    # Very old uncompressed files
                    cached_data = pickle.loads(encrypted_data)
                
            # Validate cache structure and column names
            if (isinstance(cached_data, dict) and 
                'lookup_mapping' in cached_data and 
                'lookup_records' in cached_data and
                'column_names' in cached_data and
                cached_data['column_names']['snomed'] == snomed_code_col and
                cached_data['column_names']['emis'] == emis_guid_col):
                
                return cached_data
    except Exception:
        pass
    
    return None


def _cleanup_old_cache_files(cache_dir: str, current_hash: str):
    """Remove old cache files, keeping only the current one"""
    try:
        for filename in os.listdir(cache_dir):
            if filename.startswith("emis_lookup_") and filename.endswith(".pkl"):
                if current_hash not in filename:
                    old_file = os.path.join(cache_dir, filename)
                    os.remove(old_file)
    except Exception:
        # Ignore cleanup errors
        pass


def build_emis_lookup_cache(lookup_df: pd.DataFrame, snomed_code_col: str, emis_guid_col: str, version_info: Dict = None) -> bool:
    """
    Build and cache the comprehensive EMIS lookup table data
    Uses cache-first approach: check local → check GitHub → build if needed
    
    Args:
        lookup_df: The lookup table DataFrame
        snomed_code_col: Name of the SNOMED code column
        emis_guid_col: Name of the EMIS GUID column
        
    Returns:
        bool: True if cache is available (from any source), False otherwise
    """
    if lookup_df is None or lookup_df.empty:
        return False
    
    try:
        table_hash = _get_lookup_table_hash(lookup_df, version_info)
        
        # Step 1: Check if local cache exists first (fastest)
        local_cache = _load_local_cache(table_hash, snomed_code_col, emis_guid_col)
        if local_cache is not None:
            # Local cache exists, no need to rebuild
            return True
        
        # Step 2: Try to download from GitHub as fallback
        github_cache = _download_github_cache(table_hash)
        if github_cache is not None:
            # Save GitHub cache locally for faster future access
            _save_local_cache(github_cache, table_hash)
            return True
        
        # Build comprehensive lookup data - preserve ALL records
        emis_lookup = {}
        lookup_records = {}
        all_records = []  # Store complete DataFrame records
        lookup_count = 0
        valid_mapping_count = 0
        
        for index, row in lookup_df.iterrows():
            lookup_count += 1
            
            # Store complete record for DataFrame reconstruction
            record_dict = {}
            for col in lookup_df.columns:
                record_dict[col] = row.get(col, '')
            all_records.append(record_dict)
            
            # Also build mapping dictionaries for valid records only
            snomed_code_raw = str(row.get(snomed_code_col, '')).strip()
            emis_guid = str(row.get(emis_guid_col, '')).strip()
            if snomed_code_raw and emis_guid and snomed_code_raw != 'nan':
                valid_mapping_count += 1
                
                # Normalize SNOMED code by removing .0 suffix if present
                snomed_code = snomed_code_raw[:-2] if snomed_code_raw.endswith('.0') else snomed_code_raw
                
                # Store normalized SNOMED -> EMIS GUID mapping
                emis_lookup[snomed_code] = emis_guid
                
                # Store complete record data for advanced features
                record_data = {}
                for col in lookup_df.columns:
                    if col not in [snomed_code_col, emis_guid_col]:  # Avoid duplication
                        record_data[col] = row.get(col, '')
                
                # Store using normalized SNOMED code (without .0)
                lookup_records[snomed_code] = {
                    'emis_guid': emis_guid,
                    'descendants': record_data.get('Descendants', ''),
                    'has_qualifier': record_data.get('HasQualifier', ''),
                    'is_parent': record_data.get('IsParent', ''),
                    'source_type': record_data.get('Source_Type', ''),
                    'code_type': record_data.get('CodeType', ''),
                    **record_data  # Include all other columns
                }
        
        # Step 3: Build cache from scratch
        # Save to local cache
        cache_data = {
            'lookup_mapping': emis_lookup,  # SNOMED -> EMIS GUID mapping (valid only)
            'lookup_records': lookup_records,  # SNOMED -> full record data (valid only)
            'all_records': all_records,  # Complete DataFrame records (ALL records)
            'column_names': {
                'snomed': snomed_code_col,
                'emis': emis_guid_col
            },
            'created_at': datetime.now().isoformat(),
            'record_count': lookup_count,  # Total records
            'valid_mapping_count': valid_mapping_count,  # Valid mappings only
            'table_hash': table_hash,
            'available_columns': list(lookup_df.columns),
            'original_version_info': version_info if version_info else {}  # Store original version info
        }
        
        # Save locally
        saved_locally = _save_local_cache(cache_data, table_hash)
        
        return saved_locally
        
    except Exception as e:
        # If cache building fails, log but don't crash
        st.warning(f"Could not build EMIS lookup cache: {str(e)}")
        return False


def get_latest_cached_emis_lookup() -> Optional[Tuple[pd.DataFrame, str, str, Dict]]:
    """
    Load the latest cached EMIS lookup table data without requiring hash validation
    Scans local cache directory for the most recent cache file
    
    Returns:
        Tuple of (lookup_df, emis_guid_col, snomed_code_col, version_info) or None if not cached
    """
    try:
        cache_dir = _get_cache_directory()
        
        # Find all cache files
        cache_files = []
        for filename in os.listdir(cache_dir):
            if filename.startswith("emis_lookup_") and filename.endswith(".pkl"):
                cache_file = os.path.join(cache_dir, filename)
                mtime = os.path.getmtime(cache_file)
                cache_files.append((mtime, cache_file, filename))
        
        if not cache_files:
            return None
        
        # Sort by modification time (newest first)
        cache_files.sort(reverse=True)
        latest_cache_file = cache_files[0][1]
        # Load the latest cache file
        with open(latest_cache_file, 'rb') as f:
            encrypted_data = f.read()
            
        # Decrypt and decompress
        try:
            decrypted_data = _decrypt_data(encrypted_data)
            cached_data = pickle.loads(gzip.decompress(decrypted_data))
        except Exception:
            # Fallback for old formats
            try:
                cached_data = pickle.loads(gzip.decompress(encrypted_data))
            except (gzip.BadGzipFile, OSError):
                cached_data = pickle.loads(encrypted_data)
        
        # Validate cache structure
        if (isinstance(cached_data, dict) and 
            'lookup_mapping' in cached_data and 
            'lookup_records' in cached_data and
            'column_names' in cached_data):
            
            emis_guid_col = cached_data['column_names']['emis']
            snomed_code_col = cached_data['column_names']['snomed']
            
            # Use complete records if available (new format), otherwise reconstruct from lookup_records (old format)
            if 'all_records' in cached_data:
                # New format - use complete DataFrame records
                lookup_df = pd.DataFrame(cached_data['all_records'])
            else:
                # Old format - reconstruct from filtered records (backward compatibility)
                records = []
                for snomed_code, record_data in cached_data['lookup_records'].items():
                    record = {snomed_code_col: snomed_code}
                    record[emis_guid_col] = record_data['emis_guid']
                    # Add other columns
                    for col, value in record_data.items():
                        if col not in ['emis_guid']:
                            record[col] = value
                    records.append(record)
                lookup_df = pd.DataFrame(records)
            
            # Use original version info if available, otherwise fall back to cache metadata
            if 'original_version_info' in cached_data and cached_data['original_version_info']:
                version_info = cached_data['original_version_info'].copy()
                # Add cache-specific metadata to the original version info
                version_info.update({
                    'cache_created_at': cached_data.get('created_at', ''),
                    'record_count': cached_data.get('record_count', len(lookup_df)),
                    'table_hash': cached_data.get('table_hash', ''),
                    'available_columns': cached_data.get('available_columns', [])
                })
            else:
                # Fall back to cache metadata only (for older cache files)
                version_info = {
                    'cache_created_at': cached_data.get('created_at', ''),
                    'record_count': cached_data.get('record_count', len(lookup_df)),
                    'table_hash': cached_data.get('table_hash', ''),
                    'available_columns': cached_data.get('available_columns', [])
                }
            
            return lookup_df, emis_guid_col, snomed_code_col, version_info
            
    except Exception:
        pass
    
    return None


def get_cached_emis_lookup(lookup_df: pd.DataFrame, snomed_code_col: str, emis_guid_col: str, version_info: Dict = None) -> Optional[Dict]:
    """
    Load cached EMIS lookup table data
    Uses cache-first approach: check local → check GitHub → return None
    
    Args:
        lookup_df: The lookup table DataFrame (for hash validation)
        snomed_code_col: Name of the SNOMED code column
        emis_guid_col: Name of the EMIS GUID column
        
    Returns:
        Dict with 'lookup_mapping' and 'lookup_records' or None if not cached
    """
    if lookup_df is None or lookup_df.empty:
        return None
    
    try:
        table_hash = _get_lookup_table_hash(lookup_df, version_info)
        
        # Step 1: Try local cache first (fastest)
        local_cache = _load_local_cache(table_hash, snomed_code_col, emis_guid_col)
        if local_cache is not None:
            return {
                'lookup_mapping': local_cache['lookup_mapping'],
                'lookup_records': local_cache['lookup_records']
            }
        
        # Step 2: Try to download from GitHub as fallback
        github_cache = _download_github_cache(table_hash)
        if github_cache is not None:
            # Save GitHub cache locally for faster future access
            _save_local_cache(github_cache, table_hash)
            
            # Validate and return
            if (isinstance(github_cache, dict) and 
                'lookup_mapping' in github_cache and 
                'lookup_records' in github_cache):
                return {
                    'lookup_mapping': github_cache['lookup_mapping'],
                    'lookup_records': github_cache['lookup_records']
                }
        
    except Exception as e:
        # If cache loading fails, just continue without cache
        pass
    
    return None


def get_cache_info(lookup_df: pd.DataFrame, version_info: Dict = None) -> Dict[str, str]:
    """
    Get information about the current cache status
    Checks GitHub first, then local cache
    
    Args:
        lookup_df: The lookup table DataFrame
        
    Returns:
        Dict with cache status information
    """
    if lookup_df is None or lookup_df.empty:
        return {"status": "no_data", "message": "No lookup table available"}
    
    try:
        table_hash = _get_lookup_table_hash(lookup_df, version_info)
        
        # Check local cache first (fastest)
        cache_dir = _get_cache_directory()
        cache_file = os.path.join(cache_dir, f"emis_lookup_{table_hash}.pkl")
        
        if os.path.exists(cache_file):
            # Get local cache file info
            stat = os.stat(cache_file)
            created_time = datetime.fromtimestamp(stat.st_mtime)
            file_size = stat.st_size / 1024 / 1024  # MB
            
            return {
                "status": "cached",
                "message": f"Local cache available (created {created_time.strftime('%Y-%m-%d %H:%M')}, {file_size:.1f} MB)",
                "hash": table_hash,
                "source": "local"
            }
        else:
            # Check GitHub cache as fallback (silently)
            github_cache = _download_github_cache(table_hash)
            if github_cache is not None:
                return {
                    "status": "cached",
                    "message": f"Cache available on GitHub (hash: {table_hash})",
                    "hash": table_hash,
                    "source": "github"
                }
            
            return {
                "status": "not_cached", 
                "message": "Cache not available - will need to build",
                "hash": table_hash
            }
            
    except Exception as e:
        return {"status": "error", "message": f"Cache check failed: {str(e)}"}


def generate_cache_for_github(lookup_df: pd.DataFrame, snomed_code_col: str, emis_guid_col: str, output_dir: str = ".", version_info: Dict = None) -> bool:
    """
    Generate cache file for committing to GitHub repository
    
    This function is intended to be run locally when updating the lookup table,
    to pre-generate the cache file that gets committed to the GitHub repo.
    
    Args:
        lookup_df: The lookup table DataFrame
        snomed_code_col: Name of the SNOMED code column
        emis_guid_col: Name of the EMIS GUID column
        output_dir: Directory to save the cache file (default: current directory)
        
    Returns:
        bool: True if cache file was generated successfully
    """
    if lookup_df is None or lookup_df.empty:
        print("❌ No lookup table provided")
        return False
    
    try:
        table_hash = _get_lookup_table_hash(lookup_df, version_info)
        output_file = os.path.join(output_dir, f"emis_lookup_{table_hash}.pkl")
        
        print(f"Building encrypted EMIS lookup cache for GitHub deployment...")
        print(f"Processing {len(lookup_df)} lookup table records...")
        
        # Build comprehensive lookup data - preserve ALL records (same logic as build_emis_lookup_cache)
        emis_lookup = {}
        lookup_records = {}
        all_records = []  # Store complete DataFrame records
        lookup_count = 0
        valid_mapping_count = 0
        
        for index, row in lookup_df.iterrows():
            lookup_count += 1
            
            # Store complete record for DataFrame reconstruction
            record_dict = {}
            for col in lookup_df.columns:
                record_dict[col] = row.get(col, '')
            all_records.append(record_dict)
            
            # Also build mapping dictionaries for valid records only
            snomed_code_raw = str(row.get(snomed_code_col, '')).strip()
            emis_guid = str(row.get(emis_guid_col, '')).strip()
            if snomed_code_raw and emis_guid and snomed_code_raw != 'nan':
                valid_mapping_count += 1
                
                # Normalize SNOMED code by removing .0 suffix if present
                snomed_code = snomed_code_raw[:-2] if snomed_code_raw.endswith('.0') else snomed_code_raw
                
                # Store normalized SNOMED -> EMIS GUID mapping
                emis_lookup[snomed_code] = emis_guid
                
                # Store complete record data for advanced features
                record_data = {}
                for col in lookup_df.columns:
                    if col not in [snomed_code_col, emis_guid_col]:  # Avoid duplication
                        record_data[col] = row.get(col, '')
                
                # Store using normalized SNOMED code (without .0)
                lookup_records[snomed_code] = {
                    'emis_guid': emis_guid,
                    'descendants': record_data.get('Descendants', ''),
                    'has_qualifier': record_data.get('HasQualifier', ''),
                    'is_parent': record_data.get('IsParent', ''),
                    'source_type': record_data.get('Source_Type', ''),
                    'code_type': record_data.get('CodeType', ''),
                    **record_data  # Include all other columns
                }
        
        # Create cache data structure
        cache_data = {
            'lookup_mapping': emis_lookup,  # SNOMED -> EMIS GUID mapping (valid only)
            'lookup_records': lookup_records,  # SNOMED -> full record data (valid only)
            'all_records': all_records,  # Complete DataFrame records (ALL records)
            'column_names': {
                'snomed': snomed_code_col,
                'emis': emis_guid_col
            },
            'created_at': datetime.now().isoformat(),
            'record_count': lookup_count,  # Total records
            'valid_mapping_count': valid_mapping_count,  # Valid mappings only
            'table_hash': table_hash,
            'available_columns': list(lookup_df.columns)
        }
        
        # Save to file with compression and encryption
        compressed_data = gzip.compress(pickle.dumps(cache_data, protocol=pickle.HIGHEST_PROTOCOL))
        encrypted_data = _encrypt_data(compressed_data)
        
        with open(output_file, 'wb') as f:
            f.write(encrypted_data)
        
        file_size = os.path.getsize(output_file) / 1024 / 1024  # MB
        
        print(f"SUCCESS: Encrypted cache generated successfully!")
        print(f"File: {output_file}")
        print(f"Records: {lookup_count:,}")
        print(f"Size: {file_size:.1f} MB")
        print(f"Hash: {table_hash}")
        print(f"Encryption: Protected with GZIP_TOKEN")
        print(f"")
        print(f"Next steps:")
        print(f"1. Copy {output_file} to your repository's .cache/ directory")
        print(f"2. Commit and push to make it available to all users")
        print(f"3. The encrypted cache will be automatically downloaded and decrypted by the app")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Cache generation failed: {str(e)}")
        return False