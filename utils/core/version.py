"""
ClinXML Version Information
Single source of truth for application version across all components
"""

# Application Version - Update this single location for all version references
__version__ = "2.2.4"

# Application metadata
APP_NAME = "ClinXML"
APP_FULL_NAME = "ClinXML - The Unofficial EMIS XML Toolkit"
APP_DESCRIPTION = "Comprehensive EMIS XML analysis and clinical code extraction for NHS healthcare teams"

# Version components for programmatic access
VERSION_MAJOR = 2
VERSION_MINOR = 2
VERSION_PATCH = 4

# Build information
BUILD_DATE = "20th November 2025"
BUILD_TYPE = "stable"  # stable, beta, alpha, dev

def get_version_string() -> str:
    """Return the full version string"""
    return __version__

def get_version_tuple() -> tuple:
    """Return version as tuple (major, minor, patch)"""
    return (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

def get_app_info() -> dict:
    """Return complete application information"""
    return {
        "name": APP_NAME,
        "full_name": APP_FULL_NAME,
        "description": APP_DESCRIPTION,
        "version": __version__,
        "build_date": BUILD_DATE,
        "build_type": BUILD_TYPE
    }

def get_user_agent_string() -> str:
    """Return user agent string for API calls"""
    return f"{APP_NAME}/{__version__}"

def get_export_metadata() -> dict:
    """Return metadata for exports"""
    return {
        "export_tool": APP_NAME,
        "version": __version__,
        "app_name": APP_FULL_NAME
    }
