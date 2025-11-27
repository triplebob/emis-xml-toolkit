#!/usr/bin/env python3
"""
Update README.md, changelog.md, and project-structure.md with current version information from version.py
Run this script whenever the version is updated
"""

import re
from pathlib import Path
from datetime import datetime
try:
    from .version import __version__, APP_FULL_NAME, APP_DESCRIPTION
except ImportError:
    # Handle running this script directly
    from version import __version__, APP_FULL_NAME, APP_DESCRIPTION

def update_file_versions(file_path, file_type="README"):
    """Update a file with current version information"""
    
    if not file_path.exists():
        raise FileNotFoundError(f"{file_type} not found at {file_path}")
    
    # Read current file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_made = 0
    
    # Update version references
    # Handle both simple and README.md complex patterns
    if file_type == "README":
        # Pattern: *Application Version: [X.X.X](changelog.md) • [View Release Notes](changelog.md)*
        version_pattern = r'\*Application Version: \[\d+\.\d+\.\d+\]\(changelog\.md\) • \[View Release Notes\]\(changelog\.md\)\*'
        replacement = f'*Application Version: [{__version__}](changelog.md) • [View Release Notes](changelog.md)*'
    else:
        # Pattern: *Application Version: X.X.X*
        version_pattern = r'\*Application Version: \d+\.\d+\.\d+\*'
        replacement = f'*Application Version: {__version__}*'
    
    new_content = re.sub(version_pattern, replacement, content)
    if new_content != content:
        changes_made += 1
        content = new_content
    
    # Update last updated date with day
    current_date = datetime.now()
    day = current_date.day
    # Add ordinal suffix (1st, 2nd, 3rd, 4th, etc.)
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    
    formatted_date = f"{day}{suffix} {current_date.strftime('%B %Y')}"
    date_pattern = r'\*Last Updated: [^*]+\*'
    date_replacement = f'*Last Updated: {formatted_date}*'
    new_content = re.sub(date_pattern, date_replacement, content)
    if new_content != content:
        changes_made += 1
        content = new_content
    
    # Update app description if it exists in the first paragraph
    # This is optional - only if you want to sync the description too
    new_content = re.sub(
        r'(A comprehensive web application for analysing EMIS XML files)[^.]*(\. Transform complex EMIS XML documents)',
        rf'{APP_DESCRIPTION}\2',
        content
    )
    if new_content != content:
        changes_made += 1
        content = new_content
    
    # Only write if changes were made
    if changes_made > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return formatted_date, True
    else:
        return formatted_date, False

def update_all_version_files():
    """Update all files with version information"""
    
    # Get the project root directory - handle both direct execution and UI execution
    current_file_path = Path(__file__)
    
    # Always go up three levels from utils/core/ to get to project root
    # current_file_path = E:\ClinXML\emis-xml-convertor\utils\core\update_versions.py
    # current_file_path.parent = E:\ClinXML\emis-xml-convertor\utils\core\
    # current_file_path.parent.parent = E:\ClinXML\emis-xml-convertor\utils\
    # current_file_path.parent.parent.parent = E:\ClinXML\emis-xml-convertor\
    project_root = current_file_path.parent.parent.parent
    
    updated_files = []
    formatted_date = None
    
    # Update README.md
    readme_path = project_root / "README.md"
    if readme_path.exists():
        formatted_date, was_updated = update_file_versions(readme_path, "README")
        if was_updated:
            updated_files.append("README.md")
    
    # Update changelog.md
    changelog_path = project_root / "changelog.md"
    if changelog_path.exists():
        if not formatted_date:
            # Calculate date if not done already
            current_date = datetime.now()
            day = current_date.day
            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = "th"
            else:
                suffix = ["st", "nd", "rd"][day % 10 - 1]
            formatted_date = f"{day}{suffix} {current_date.strftime('%B %Y')}"
        
        _, was_updated = update_file_versions(changelog_path, "changelog")
        if was_updated:
            updated_files.append("changelog.md")
    
    # Update project-structure.md
    project_structure_path = project_root / "docs" / "project-structure.md"
    if project_structure_path.exists():
        if not formatted_date:
            # Calculate date if not done already
            current_date = datetime.now()
            day = current_date.day
            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = "th"
            else:
                suffix = ["st", "nd", "rd"][day % 10 - 1]
            formatted_date = f"{day}{suffix} {current_date.strftime('%B %Y')}"
        
        _, was_updated = update_file_versions(project_structure_path, "project-structure")
        if was_updated:
            updated_files.append("docs/project-structure.md")
    
    return updated_files, formatted_date

def main():
    """Main entry point"""
    try:
        updated_files, formatted_date = update_all_version_files()
        
        print(f"[OK] Updated {len(updated_files)} files to version {__version__}")
        for file in updated_files:
            print(f"[INFO] - {file}")
        if formatted_date:
            print(f"[INFO] Last updated set to: {formatted_date}")
            
    except Exception as e:
        print(f"[ERROR] Error updating files: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
