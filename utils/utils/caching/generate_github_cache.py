"""
GitHub Cache Generator

Run this script to generate the EMIS lookup cache file for committing to GitHub.
This allows all users to download the pre-built cache instead of building it themselves.

Usage:
    python utils/utils/caching/generate_github_cache.py
"""

import sys
import os

# Add the project root to the path so we can import our modules
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

from utils.utils.lookup import load_lookup_table
from utils.utils.caching.lookup_cache import generate_cache_for_github


def main():
    """Generate the GitHub cache file"""
    print("EMIS Lookup Cache Generator for GitHub")
    print("=" * 50)
    print("Cache will be encrypted using GZIP_TOKEN from secrets")
    print("")
    
    try:
        # Load the lookup table
        print("Loading lookup table...")
        lookup_df, emis_guid_col, snomed_code_col, version_info = load_lookup_table()
        
        if lookup_df is None or lookup_df.empty:
            print("ERROR: Failed to load lookup table")
            return False
        
        print(f"SUCCESS: Loaded lookup table: {len(lookup_df):,} records")
        print(f"SNOMED column: {snomed_code_col}")
        print(f"EMIS GUID column: {emis_guid_col}")
        
        if version_info:
            if 'emis_version' in version_info:
                print(f"EMIS version: {version_info['emis_version']}")
            if 'snomed_version' in version_info:
                print(f"SNOMED version: {version_info['snomed_version']}")
        
        print("")
        
        # Generate the cache file
        success = generate_cache_for_github(
            lookup_df=lookup_df,
            snomed_code_col=snomed_code_col,
            emis_guid_col=emis_guid_col,
            output_dir=".cache",
            version_info=version_info
        )
        
        if success:
            print("SUCCESS: Cache generation completed successfully!")
            return True
        else:
            print("ERROR: Cache generation failed")
            return False
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
