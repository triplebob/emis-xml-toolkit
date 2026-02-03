"""
EMIS Lookup Table Cache Management

Handles encrypted parquet storage for the EMIS-SNOMED lookup table.
Data is encrypted at rest and only decrypted in memory during use.
"""

import gzip
import hashlib
import io
import os
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any

import pandas as pd
import pyarrow.parquet as pq
import streamlit as st
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# ---------------------------------------------------------------------------
# Encryption utilities
# ---------------------------------------------------------------------------

def _get_encryption_key() -> Optional[bytes]:
    """Derive encryption key from GZIP_TOKEN in Streamlit secrets."""
    try:
        password = st.secrets["GZIP_TOKEN"]
        salt = b'emis_parquet_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    except KeyError:
        return None
    except Exception:
        return None


def _encrypt_bytes(data: bytes) -> bytes:
    """Encrypt and compress bytes using GZIP_TOKEN-derived key."""
    key = _get_encryption_key()
    if key is None:
        raise ValueError("GZIP_TOKEN not found in secrets - cannot encrypt")
    fernet = Fernet(key)
    compressed = gzip.compress(data, compresslevel=9)
    return fernet.encrypt(compressed)


def _decrypt_bytes(encrypted_data: bytes) -> bytes:
    """Decrypt and decompress bytes using GZIP_TOKEN-derived key."""
    key = _get_encryption_key()
    if key is None:
        raise ValueError("GZIP_TOKEN not found in secrets - cannot decrypt")
    try:
        fernet = Fernet(key)
        compressed = fernet.decrypt(encrypted_data)
        return gzip.decompress(compressed)
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")


# ---------------------------------------------------------------------------
# Cache directory management
# ---------------------------------------------------------------------------

def get_cache_directory() -> str:
    """Get or create the cache directory in repository root."""
    repo_root = Path(__file__).resolve().parents[2]
    cache_dir = repo_root / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir)


def cleanup_old_cache_files(cache_dir: str, keep_pattern: str = None):
    """Remove stale cache files, optionally keeping files matching a pattern."""
    try:
        for filename in os.listdir(cache_dir):
            if filename.startswith("emis_lookup_") and filename.endswith(".enc"):
                if keep_pattern and keep_pattern in filename:
                    continue
                old_file = os.path.join(cache_dir, filename)
                os.remove(old_file)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Filtered parquet loading
# ---------------------------------------------------------------------------

def load_filtered_lookup(
    encrypted_bytes: bytes,
    emis_guids: List[str],
    emis_guid_col: str = "EMIS_GUID",
) -> pd.DataFrame:
    """
    Decrypt parquet and load only rows matching the given EMIS GUIDs.

    Args:
        encrypted_bytes: Encrypted parquet file content
        emis_guids: List of EMIS GUIDs to filter by
        emis_guid_col: Name of the EMIS GUID column

    Returns:
        Filtered DataFrame containing only matching rows
    """
    if not emis_guids:
        return pd.DataFrame()

    # Decrypt to memory
    parquet_bytes = _decrypt_bytes(encrypted_bytes)

    # Read full parquet then filter (more efficient than PyArrow IN filter for large lists)
    table = pq.read_table(io.BytesIO(parquet_bytes))
    df = table.to_pandas()

    # Filter by EMIS GUIDs
    guid_set = set(str(g).strip() for g in emis_guids if g)
    df[emis_guid_col] = df[emis_guid_col].astype(str).str.strip()
    return df[df[emis_guid_col].isin(guid_set)]


def build_lookup_dicts(
    df: pd.DataFrame,
    emis_guid_col: str = "EMIS_GUID",
    snomed_code_col: str = "SNOMED_Code",
) -> Dict[str, Dict[str, Any]]:
    """
    Build lookup dictionaries from a filtered DataFrame.

    Args:
        df: Filtered DataFrame with lookup data
        emis_guid_col: Name of EMIS GUID column
        snomed_code_col: Name of SNOMED code column

    Returns:
        Dict with 'guid_to_snomed' and 'guid_to_record' lookup dicts
    """
    if df is None or df.empty:
        return {"guid_to_snomed": {}, "guid_to_record": {}}

    df = df.copy()
    df[emis_guid_col] = df[emis_guid_col].astype(str).str.strip()

    guid_to_snomed = {}
    guid_to_record = {}

    for _, row in df.iterrows():
        guid = row.get(emis_guid_col, "")
        snomed = row.get(snomed_code_col, "")

        if guid:
            # Normalise SNOMED code
            if snomed and str(snomed) != "nan":
                snomed_str = str(snomed)
                if snomed_str.endswith(".0"):
                    snomed_str = snomed_str[:-2]
                guid_to_snomed[guid] = snomed_str

            # Build full record
            guid_to_record[guid] = {
                "snomed_code": guid_to_snomed.get(guid, ""),
                "descendants": str(row.get("Descendants", "")) if "Descendants" in df.columns else "",
                "has_qualifier": str(row.get("HasQualifier", "")) if "HasQualifier" in df.columns else "",
                "is_parent": str(row.get("IsParent", "")) if "IsParent" in df.columns else "",
                "source_type": str(row.get("Source_Type", "")) if "Source_Type" in df.columns else "",
                "code_type": str(row.get("CodeType", "")) if "CodeType" in df.columns else "",
            }

    return {"guid_to_snomed": guid_to_snomed, "guid_to_record": guid_to_record}


def get_parquet_metadata(encrypted_bytes: bytes) -> Dict[str, Any]:
    """
    Get metadata from encrypted parquet without loading all data.

    Args:
        encrypted_bytes: Encrypted parquet content

    Returns:
        Dict with row count, columns, etc.
    """
    try:
        parquet_bytes = _decrypt_bytes(encrypted_bytes)
        pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
        metadata = pf.metadata
        schema = pf.schema_arrow

        return {
            "num_rows": metadata.num_rows,
            "num_columns": metadata.num_columns,
            "columns": [schema.field(i).name for i in range(len(schema))],
            "created_by": metadata.created_by,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Cache generation for GitHub deployment
# ---------------------------------------------------------------------------

def generate_encrypted_parquet(
    source_parquet_path: str,
    output_dir: str = None,
    version_info: Dict = None,
) -> bool:
    """
    Generate encrypted parquet file for GitHub deployment.

    Run this locally when you need to update the lookup table:
    1. Place the source parquet in a known location
    2. Run this function to encrypt it
    3. Upload the .enc file to GitHub .cache/ directory

    Args:
        source_parquet_path: Path to the unencrypted source parquet file
        output_dir: Output directory (defaults to .cache/)
        version_info: Version metadata dict for filename hash

    Returns:
        True if successful
    """
    if not os.path.exists(source_parquet_path):
        print(f"ERROR: Source file not found: {source_parquet_path}")
        return False

    try:
        # Read source parquet
        print(f"Reading source parquet: {source_parquet_path}")
        with open(source_parquet_path, 'rb') as f:
            parquet_bytes = f.read()

        # Get metadata for reporting
        pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
        num_rows = pf.metadata.num_rows
        source_size_mb = len(parquet_bytes) / (1024 * 1024)

        print(f"Source: {num_rows:,} rows, {source_size_mb:.1f} MB")

        # Generate hash for filename
        if version_info:
            hash_data = (
                f"emis_{version_info.get('emis_version', '')}_"
                f"snomed_{version_info.get('snomed_version', '')}_"
                f"extract_{version_info.get('extract_date', '')}"
            )
            table_hash = hashlib.md5(hash_data.encode()).hexdigest()[:12]
        else:
            # Fallback: hash the parquet content
            table_hash = hashlib.md5(parquet_bytes).hexdigest()[:12]

        # Encrypt
        print("Encrypting parquet data...")
        encrypted_bytes = _encrypt_bytes(parquet_bytes)
        encrypted_size_mb = len(encrypted_bytes) / (1024 * 1024)

        # Output path
        if output_dir is None:
            output_dir = get_cache_directory()
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"emis_lookup_{table_hash}.enc")

        # Write encrypted file
        with open(output_file, 'wb') as f:
            f.write(encrypted_bytes)

        print(f"")
        print(f"SUCCESS: Encrypted parquet generated")
        print(f"  File: {output_file}")
        print(f"  Rows: {num_rows:,}")
        print(f"  Source size: {source_size_mb:.1f} MB")
        print(f"  Encrypted size: {encrypted_size_mb:.1f} MB")
        print(f"  Hash: {table_hash}")
        print(f"")
        print(f"Next steps:")
        print(f"  1. Upload {os.path.basename(output_file)} to GitHub .cache/ directory")
        print(f"  2. Update lookup-version.json with version info")
        print(f"  3. Commit and push")

        return True

    except Exception as e:
        print(f"ERROR: Encryption failed: {str(e)}")
        return False


# ---------------------------------------------------------------------------
# Compatibility functions for terminology server integration
# ---------------------------------------------------------------------------

def get_cached_emis_lookup(lookup_df, snomed_code_col, emis_guid_col, version_info=None) -> Optional[Dict[str, Any]]:
    """
    Compatibility wrapper for terminology server features.

    With the encrypted parquet architecture, this function provides
    lookup mappings built from a filtered DataFrame if available,
    or returns None to indicate lookup not available.

    The terminology server expansion workflow needs reverse lookups
    (SNOMED → EMIS GUID) which requires different handling.
    """
    import streamlit as st
    from ..system.session_state import SessionStateKeys

    # Check if we have encrypted bytes in session
    encrypted_bytes = st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES)
    if encrypted_bytes is None:
        return None

    # For terminology server, we need the full reverse mapping
    # This is a fallback that loads and builds the full lookup
    # (used only for terminology server features, not main XML processing)
    try:
        parquet_bytes = _decrypt_bytes(encrypted_bytes)
        table = pq.read_table(io.BytesIO(parquet_bytes))
        df = table.to_pandas()

        # Build SNOMED → EMIS mapping (reverse of normal lookup)
        lookup_mapping = {}
        lookup_records = {}

        for _, row in df.iterrows():
            emis_guid = str(row.get(emis_guid_col, "")).strip()
            snomed_raw = str(row.get(snomed_code_col, "")).strip()

            if not emis_guid or not snomed_raw or snomed_raw == "nan":
                continue

            # Normalise SNOMED code
            snomed_code = snomed_raw[:-2] if snomed_raw.endswith(".0") else snomed_raw

            # SNOMED → EMIS GUID (for reverse lookups)
            lookup_mapping[snomed_code] = emis_guid

            # SNOMED → full record
            lookup_records[snomed_code] = {
                "emis_guid": emis_guid,
                "descendants": str(row.get("Descendants", "")) if "Descendants" in df.columns else "",
                "has_qualifier": str(row.get("HasQualifier", "")) if "HasQualifier" in df.columns else "",
                "is_parent": str(row.get("IsParent", "")) if "IsParent" in df.columns else "",
                "source_type": str(row.get("Source_Type", "")) if "Source_Type" in df.columns else "",
                "code_type": str(row.get("CodeType", "")) if "CodeType" in df.columns else "",
            }

        return {
            "lookup_mapping": lookup_mapping,
            "lookup_records": lookup_records,
        }
    except Exception:
        return None


def build_emis_lookup_cache(lookup_df, snomed_code_col, emis_guid_col, version_info=None) -> bool:
    """
    Compatibility stub - cache building is now handled by generate_encrypted_parquet.
    Returns True to indicate success (no-op in the current architecture).
    """
    return True


def get_cache_info(lookup_df, version_info=None) -> Dict[str, str]:
    """
    Compatibility stub - returns status indicating cache is available.
    """
    return {"status": "cached", "message": "Using encrypted parquet architecture"}


def generate_cache_for_github(lookup_df, snomed_code_col, emis_guid_col, output_dir=".", version_info=None) -> bool:
    """
    Compatibility wrapper - redirects to generate_from_dataframe.
    """
    return generate_from_dataframe(lookup_df, output_dir, version_info)


def generate_from_dataframe(
    lookup_df: pd.DataFrame,
    output_dir: str = None,
    version_info: Dict = None,
) -> bool:
    """
    Generate encrypted parquet from a DataFrame.

    Convenience wrapper for when you have the lookup data as a DataFrame
    (e.g., from CSV or database export).

    Args:
        lookup_df: DataFrame with lookup data
        output_dir: Output directory (defaults to .cache/)
        version_info: Version metadata dict

    Returns:
        True if successful
    """
    if lookup_df is None or lookup_df.empty:
        print("ERROR: Empty DataFrame provided")
        return False

    try:
        # Convert to parquet bytes
        print(f"Converting DataFrame ({len(lookup_df):,} rows) to parquet...")
        buffer = io.BytesIO()
        lookup_df.to_parquet(buffer, engine='pyarrow', compression='snappy')
        parquet_bytes = buffer.getvalue()

        # Generate hash
        if version_info:
            hash_data = (
                f"emis_{version_info.get('emis_version', '')}_"
                f"snomed_{version_info.get('snomed_version', '')}_"
                f"extract_{version_info.get('extract_date', '')}"
            )
            table_hash = hashlib.md5(hash_data.encode()).hexdigest()[:12]
        else:
            table_hash = hashlib.md5(parquet_bytes).hexdigest()[:12]

        # Encrypt
        print("Encrypting...")
        encrypted_bytes = _encrypt_bytes(parquet_bytes)

        # Output path
        if output_dir is None:
            output_dir = get_cache_directory()
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"emis_lookup_{table_hash}.enc")

        # Write
        with open(output_file, 'wb') as f:
            f.write(encrypted_bytes)

        source_mb = len(parquet_bytes) / (1024 * 1024)
        enc_mb = len(encrypted_bytes) / (1024 * 1024)

        print(f"")
        print(f"SUCCESS: Encrypted parquet generated")
        print(f"  File: {output_file}")
        print(f"  Rows: {len(lookup_df):,}")
        print(f"  Parquet size: {source_mb:.1f} MB")
        print(f"  Encrypted size: {enc_mb:.1f} MB")
        print(f"  Hash: {table_hash}")

        return True

    except Exception as e:
        print(f"ERROR: Generation failed: {str(e)}")
        return False
