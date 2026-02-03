"""
Terminology server connection helpers.
"""

from typing import Tuple

from .service import get_expansion_service


def test_connection(client_id: str, client_secret: str) -> Tuple[bool, str]:
    """Test NHS Terminology Server connectivity using configured credentials."""
    try:
        service = get_expansion_service()
        if not service.client:
            service.configure_credentials(client_id, client_secret)
        return service.client.test_connection()
    except Exception as exc:
        return False, f"Connection test error: {exc}"
