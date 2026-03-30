from fastapi import Request


async def get_request_id(request: Request) -> str:
    """Extract or generate request ID for tracing"""
    return request.headers.get("X-Request-ID", "unknown")


def get_telecom_context(gnb_id: str, cell_id: str = None) -> dict:
    """Build telecom-specific context for logging"""
    return {
        "network_element": "gNB",
        "element_id": gnb_id,
        "cell_id": cell_id,
        "domain": "RAN",
        "technology": "5G_NR"
    }