"""
Lookup Table Manager

Coordinates loading encrypted parquet from local cache or generating
from private repo. Provides filtered lookups for XML processing.
"""

import streamlit as st
from typing import Dict, Tuple, Any, Optional, List

from .lookup_cache import (
    load_filtered_lookup,
    build_lookup_dicts,
    get_cache_directory,
    _encrypt_bytes,
    _decrypt_bytes,
    cleanup_old_cache_files,
)
from ..system.session_state import SessionStateKeys
from ..system.update_versions import get_lookup_version_info, clear_lookup_version_cache
from ..ui.theme import info_box, success_box, warning_box


def load_lookup_table() -> Tuple[bytes, str, str, Dict[str, Any]]:
    """
    Load the encrypted lookup table from local cache or generate from private repo.

    Flow:
    1. Check session state for already loaded bytes
    2. Check .cache/ for existing .enc file
    3. If not found, download raw parquet from private repo, encrypt, save

    Returns:
        Tuple of (encrypted_bytes, emis_guid_col, snomed_code_col, version_info)

    Raises:
        Exception: If loading fails
    """
    try:
        # Check if already loaded in session state
        encrypted_bytes = st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES)
        emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL)
        snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL)
        version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})

        if encrypted_bytes is not None and emis_guid_col and snomed_code_col:
            return encrypted_bytes, emis_guid_col, snomed_code_col, version_info

        # Try to load from local .enc file first
        try:
            local_result = _load_from_local_cache()
            if local_result is not None:
                encrypted_bytes, emis_guid_col, snomed_code_col, version_info = local_result
                version_info['load_source'] = 'cache'

                # Store in session state
                st.session_state[SessionStateKeys.LOOKUP_ENCRYPTED_BYTES] = encrypted_bytes
                st.session_state[SessionStateKeys.EMIS_GUID_COL] = emis_guid_col
                st.session_state[SessionStateKeys.SNOMED_CODE_COL] = snomed_code_col
                st.session_state[SessionStateKeys.LOOKUP_VERSION_INFO] = version_info

                return encrypted_bytes, emis_guid_col, snomed_code_col, version_info
        except Exception:
            pass

        # No local cache - generate from private repo
        st.markdown(info_box("Generating lookup cache from private repo..."), unsafe_allow_html=True)

        result = generate_encrypted_lookup(show_progress=True)
        if result is None:
            raise Exception("Failed to generate encrypted lookup")

        encrypted_bytes, emis_guid_col, snomed_code_col, version_info = result
        version_info['load_source'] = 'github'

        # Store in session state
        st.session_state[SessionStateKeys.LOOKUP_ENCRYPTED_BYTES] = encrypted_bytes
        st.session_state[SessionStateKeys.EMIS_GUID_COL] = emis_guid_col
        st.session_state[SessionStateKeys.SNOMED_CODE_COL] = snomed_code_col
        st.session_state[SessionStateKeys.LOOKUP_VERSION_INFO] = version_info

        st.markdown(success_box("Lookup table generated successfully"), unsafe_allow_html=True)

        return encrypted_bytes, emis_guid_col, snomed_code_col, version_info

    except KeyError as e:
        raise Exception(f"Required secret not found: {e}")
    except Exception as e:
        raise Exception(f"Error loading lookup table: {str(e)}")


def _load_from_local_cache() -> Optional[Tuple[bytes, str, str, Dict[str, Any]]]:
    """Try to load encrypted parquet from local .cache directory."""
    import os
    import io
    import pyarrow.parquet as pq

    cache_dir = get_cache_directory()

    # Find most recent .enc file
    enc_files = []
    try:
        for filename in os.listdir(cache_dir):
            if filename.startswith("emis_lookup_") and filename.endswith(".enc"):
                filepath = os.path.join(cache_dir, filename)
                mtime = os.path.getmtime(filepath)
                enc_files.append((mtime, filepath))
    except FileNotFoundError:
        return None

    if not enc_files:
        return None

    enc_files.sort(reverse=True)
    latest_file = enc_files[0][1]

    # Read encrypted bytes
    with open(latest_file, 'rb') as f:
        encrypted_bytes = f.read()

    # Validate and get column names
    parquet_bytes = _decrypt_bytes(encrypted_bytes)
    pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
    columns = [pf.schema_arrow.field(i).name for i in range(len(pf.schema_arrow))]

    emis_guid_col = None
    snomed_code_col = None
    for col in columns:
        if col in ['EMIS_GUID', 'CodeId', 'emis_guid']:
            emis_guid_col = col
        if col in ['SNOMED_Code', 'ConceptId', 'snomed_code']:
            snomed_code_col = col

    if not emis_guid_col or not snomed_code_col:
        return None

    # Fetch version info from private repo
    version_info = get_lookup_version_info()

    return encrypted_bytes, emis_guid_col, snomed_code_col, version_info


def _save_to_local_cache(encrypted_bytes: bytes, version_info: Dict[str, Any]) -> bool:
    """Save encrypted bytes to local cache for faster future loads."""
    import os
    import hashlib

    try:
        cache_dir = get_cache_directory()

        # Generate hash for filename
        if version_info:
            hash_data = (
                f"emis_{version_info.get('emis_version', '')}_"
                f"snomed_{version_info.get('snomed_version', '')}_"
                f"extract_{version_info.get('extract_date', '')}"
            )
            table_hash = hashlib.md5(hash_data.encode()).hexdigest()[:12]
        else:
            table_hash = hashlib.md5(encrypted_bytes).hexdigest()[:12]

        # Save encrypted parquet
        output_file = os.path.join(cache_dir, f"emis_lookup_{table_hash}.enc")
        with open(output_file, 'wb') as f:
            f.write(encrypted_bytes)

        # Cleanup stale .enc files
        cleanup_old_cache_files(cache_dir, table_hash)

        return True

    except Exception:
        return False  # Cache save may fail on read-only systems


def generate_encrypted_lookup(show_progress: bool = False) -> Optional[Tuple[bytes, str, str, Dict[str, Any]]]:
    """
    Download raw parquet from private repo and generate encrypted version.

    Args:
        show_progress: Whether to show progress messages in Streamlit

    Returns:
        Tuple of (encrypted_bytes, emis_guid_col, snomed_code_col, version_info) or None
    """
    import io
    import requests
    import pyarrow.parquet as pq

    try:
        # Get credentials
        url = st.secrets["LOOKUP_TABLE_URL"]
        token = st.secrets["GITHUB_TOKEN"]

        # Download raw parquet via GitHub API
        api_url = _convert_to_api_url(url)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw"
        }

        response = requests.get(api_url, headers=headers, timeout=120)
        response.raise_for_status()

        # Handle API response
        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            import base64
            data = response.json()
            if 'content' in data:
                parquet_bytes = base64.b64decode(data['content'])
            elif 'download_url' in data:
                dl_response = requests.get(data['download_url'], headers=headers, timeout=120)
                dl_response.raise_for_status()
                parquet_bytes = dl_response.content
            else:
                raise Exception("Unexpected API response format")
        else:
            parquet_bytes = response.content

        # Get column info
        pf = pq.ParquetFile(io.BytesIO(parquet_bytes))
        columns = [pf.schema_arrow.field(i).name for i in range(len(pf.schema_arrow))]

        emis_guid_col = None
        snomed_code_col = None
        for col in columns:
            if col in ['EMIS_GUID', 'CodeId', 'emis_guid']:
                emis_guid_col = col
            if col in ['SNOMED_Code', 'ConceptId', 'snomed_code']:
                snomed_code_col = col

        if not emis_guid_col or not snomed_code_col:
            raise Exception(f"Required columns not found. Available: {columns}")

        # Fetch version info from private repo
        clear_lookup_version_cache()  # Clear cache to get fresh data
        version_info = get_lookup_version_info(token)

        # Encrypt
        encrypted_bytes = _encrypt_bytes(parquet_bytes)

        # Try to save to local cache
        saved = _save_to_local_cache(encrypted_bytes, version_info)
        if saved and show_progress:
            st.markdown(success_box("Encrypted lookup saved to local cache"), unsafe_allow_html=True)

        return encrypted_bytes, emis_guid_col, snomed_code_col, version_info

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            raise Exception("Authentication failed - check GitHub token")
        elif e.response.status_code == 403:
            raise Exception("Access forbidden - check token permissions")
        elif e.response.status_code == 404:
            raise Exception("Lookup file not found in private repo")
        raise Exception(f"GitHub API error: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to generate encrypted lookup: {str(e)}")


def _convert_to_api_url(url: str) -> str:
    """Convert raw GitHub URL to API URL."""
    if 'raw/refs/heads/main' in url:
        main_idx = url.index('raw/refs/heads/main/') + len('raw/refs/heads/main/')
        file_path = url[main_idx:]
        parts = url.split('/')
        user = parts[3]
        repo = parts[4]
        return f"https://api.github.com/repos/{user}/{repo}/contents/{file_path}"
    return url


def force_regenerate_lookup() -> bool:
    """
    Force regenerate the encrypted lookup from private repo.
    Called from sidebar button.

    Returns:
        True if successful
    """
    try:
        result = generate_encrypted_lookup(show_progress=True)
        if result is None:
            return False

        encrypted_bytes, emis_guid_col, snomed_code_col, version_info = result
        version_info['load_source'] = 'github'

        # Update session state
        st.session_state[SessionStateKeys.LOOKUP_ENCRYPTED_BYTES] = encrypted_bytes
        st.session_state[SessionStateKeys.EMIS_GUID_COL] = emis_guid_col
        st.session_state[SessionStateKeys.SNOMED_CODE_COL] = snomed_code_col
        st.session_state[SessionStateKeys.LOOKUP_VERSION_INFO] = version_info

        return True

    except Exception as e:
        st.error(f"Failed to regenerate lookup: {str(e)}")
        return False


def get_lookup_for_guids(emis_guids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get lookup dictionaries for a specific set of EMIS GUIDs.

    This is the main function used during XML processing. It:
    1. Gets encrypted bytes from session state
    2. Decrypts and filters to only matching GUIDs
    3. Returns lookup dicts for enrichment

    Args:
        emis_guids: List of EMIS GUIDs to look up

    Returns:
        Dict with 'guid_to_snomed' and 'guid_to_record' lookup dicts
    """
    if not emis_guids:
        return {"guid_to_snomed": {}, "guid_to_record": {}}

    # Get encrypted bytes from session state
    encrypted_bytes = st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES)
    emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL, "EMIS_GUID")
    snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL, "SNOMED_Code")

    if encrypted_bytes is None:
        return {"guid_to_snomed": {}, "guid_to_record": {}}

    # Load filtered DataFrame
    filtered_df = load_filtered_lookup(encrypted_bytes, emis_guids, emis_guid_col)

    # Build lookup dicts
    return build_lookup_dicts(filtered_df, emis_guid_col, snomed_code_col)


def get_lookup_statistics() -> Dict[str, Any]:
    """
    Get lookup table statistics from version_info.

    Statistics are pre-computed during parquet generation and stored
    in version_info, avoiding the need to load the full DataFrame.

    Returns:
        Dict with statistics
    """
    version_info = st.session_state.get(SessionStateKeys.LOOKUP_VERSION_INFO, {})

    def _to_int(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        text = str(value).replace(",", "").strip()
        return int(text) if text.isdigit() else 0

    clinical = _to_int(version_info.get('total_clinical_codes', 0))
    medication = _to_int(version_info.get('total_medication_codes', 0))
    total = _to_int(version_info.get('total_records', 0)) or (clinical + medication)
    other = max(0, total - clinical - medication)

    return {
        'total_count': total,
        'clinical_count': clinical,
        'medication_count': medication,
        'other_count': other,
        'emis_version': version_info.get('emis_version', 'Unknown'),
        'snomed_version': version_info.get('snomed_version', 'Unknown'),
        'extract_date': version_info.get('extract_date', 'Unknown'),
        'load_source': version_info.get('load_source', 'Unknown'),
    }


def is_lookup_loaded() -> bool:
    """Check if the lookup table is loaded in session state."""
    return st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES) is not None


def get_full_lookup_df():
    """
    Load and return the full lookup DataFrame.

    This is a compatibility function for features that need the full DataFrame
    (e.g., snomed_translation, terminology server expansion).

    Note: This loads the full DataFrame into memory. Use sparingly and
    prefer filtered lookups (get_lookup_for_guids) when possible.

    Returns:
        Tuple of (lookup_df, emis_guid_col, snomed_code_col) or (None, None, None)
    """
    import io
    import pandas as pd
    import pyarrow.parquet as pq
    from .lookup_cache import _decrypt_bytes

    encrypted_bytes = st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES)
    emis_guid_col = st.session_state.get(SessionStateKeys.EMIS_GUID_COL, "EMIS_GUID")
    snomed_code_col = st.session_state.get(SessionStateKeys.SNOMED_CODE_COL, "SNOMED_Code")

    if encrypted_bytes is None:
        return None, None, None

    try:
        parquet_bytes = _decrypt_bytes(encrypted_bytes)
        table = pq.read_table(io.BytesIO(parquet_bytes))
        lookup_df = table.to_pandas()
        return lookup_df, emis_guid_col, snomed_code_col
    except Exception:
        return None, None, None


def create_lookup_dictionaries(lookup_df, emis_guid_col, snomed_code_col):
    """
    Compatibility wrapper for snomed_translation.py.

    Creates lookup dictionaries from a DataFrame for GUID to SNOMED translation.
    In the current architecture, this is typically called with a filtered DataFrame
    or used during the translation phase.

    Returns:
        Tuple of (guid_to_snomed_dict, snomed_to_info_dict)
    """
    import time
    import pandas as pd

    guid_to_snomed_dict = {}
    snomed_to_info_dict = {}

    if lookup_df is None or lookup_df.empty:
        return guid_to_snomed_dict, snomed_to_info_dict

    start_time = time.time()

    # Convert to series for faster processing
    code_ids = lookup_df[emis_guid_col].astype(str).str.strip()
    snomed_values = lookup_df[snomed_code_col]
    source_types = lookup_df.get('Source_Type', pd.Series(['Unknown'] * len(lookup_df))).astype(str).str.strip()

    # Handle SNOMED code conversion
    concept_ids = pd.Series(index=snomed_values.index, dtype=str)
    float_mask = pd.api.types.is_float_dtype(snomed_values) & snomed_values.notna()
    integer_floats = float_mask & (snomed_values % 1 == 0)

    concept_ids[integer_floats] = snomed_values[integer_floats].astype(int).astype(str)
    concept_ids[~integer_floats] = snomed_values[~integer_floats].astype(str).str.strip()

    # Get additional columns with defaults
    has_qualifiers = lookup_df.get('HasQualifier', pd.Series(['Unknown'] * len(lookup_df))).astype(str).str.strip()
    is_parents = lookup_df.get('IsParent', pd.Series(['Unknown'] * len(lookup_df))).astype(str).str.strip()
    descendants = lookup_df.get('Descendants', pd.Series(['0'] * len(lookup_df))).astype(str).str.strip()
    code_types = lookup_df.get('CodeType', pd.Series(['Unknown'] * len(lookup_df))).astype(str).str.strip()

    # Create masks for valid entries
    valid_mask = (
        code_ids.notna() &
        (code_ids != 'nan') &
        (code_ids != '') &
        concept_ids.notna() &
        (concept_ids != 'nan') &
        (concept_ids != '')
    )

    # Build dictionaries
    for idx in lookup_df.index[valid_mask]:
        code_id = code_ids[idx]
        concept_id = concept_ids[idx]

        entry_data = {
            'snomed_code': concept_id,
            'source_type': source_types[idx],
            'has_qualifier': has_qualifiers[idx],
            'is_parent': is_parents[idx],
            'descendants': descendants[idx],
            'code_type': code_types[idx]
        }

        guid_to_snomed_dict[code_id] = entry_data
        snomed_to_info_dict[concept_id] = entry_data

    return guid_to_snomed_dict, snomed_to_info_dict
