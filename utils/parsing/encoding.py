"""
XML encoding utilities.

Provides robust decoding that prefers the XML declaration, then UTF-8, then
chardet guesses with safe fallbacks, to preserve special characters in
display names.
"""

from __future__ import annotations
import re
from typing import Optional, Tuple

import chardet


def decode_xml_bytes(raw_bytes: bytes) -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Decode raw XML bytes using a priority order:
    1) Declared encoding in the XML prolog (if present)
    2) UTF-8
    3) chardet guess
    4) latin-1 fallback
    Returns the decoded string and encoding diagnostics.
    """

    def _declared_encoding(data: bytes) -> Optional[str]:
        try:
            match = re.search(rb'<\?xml[^>]*encoding=["\\\']([^"\\\']+)["\\\']', data[:400], re.IGNORECASE)
            if match:
                return match.group(1).decode("ascii", errors="ignore")
        except Exception:
            return None
        return None

    declared = _declared_encoding(raw_bytes)
    sample_size = min(10240, len(raw_bytes))
    detected = chardet.detect(raw_bytes[:sample_size])
    guessed = detected.get("encoding") or None

    xml_content = None
    encoding_used = None
    for enc in [declared, "utf-8", guessed, "latin-1"]:
        if not enc:
            continue
        try:
            xml_content = raw_bytes.decode(enc)
            encoding_used = enc
            break
        except Exception:
            continue

    if xml_content is None:
        encoding_used = guessed or "utf-8"
        xml_content = raw_bytes.decode(encoding_used, errors="replace")

    return xml_content, encoding_used, declared, guessed
