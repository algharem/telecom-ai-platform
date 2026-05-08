"""gNB ID normalization utilities"""

def normalize_gnb_id(gnb_id: str) -> str:
    """
    Normalize gNB ID to standard format: gNB-XXX (dash separator).
    
    Handles:
    - gNB_001 -> gNB-001
    - gNB-001 -> gNB-001 (no change)
    - gNB001 -> gNB-001
    - 001 -> gNB-001
    
    Args:
        gnb_id: Input gNB identifier
    
    Returns:
        Normalized gNB ID in format gNB-XXX
    """
    if not gnb_id:
        return "gNB-001"
    
    gnb_id = gnb_id.strip()
    
    # Replace underscore with dash
    gnb_id = gnb_id.replace('_', '-')
    
    # Remove any existing gNB prefix if present and re-add
    if gnb_id.startswith('gNB-') or gnb_id.startswith('gNB_'):
        # Already has prefix, just clean it up
        suffix = gnb_id[4:] if len(gnb_id) > 4 else "001"
        gnb_id = f"gNB-{suffix}"
    elif gnb_id.startswith('gNB'):
        # Has gNB but no separator
        suffix = gnb_id[3:] if len(gnb_id) > 3 else "001"
        gnb_id = f"gNB-{suffix}"
    else:
        # Just a number or unknown format
        gnb_id = f"gNB-{gnb_id}"
    
    return gnb_id
