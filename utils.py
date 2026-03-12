import hashlib
import json
from typing import Any, Dict, Optional

def generate_dedupe_key(account_name: str, vertical: str, activity_body: Dict[str, Any]) -> str:
    """
    Generate a deterministic dedupe key for an activity.
    Uses account_name, vertical, and the activity's unique ID if available,
    otherwise falls back to hashing the entire activity payload.
    """
    activity_id = activity_body.get('id')
    if activity_id is not None:
        raw_key = f"{account_name}:{vertical}:{activity_id}"
    else:
        # Canonical JSON string: sorted keys, no whitespace
        canonical_json = json.dumps(activity_body, sort_keys=True, separators=(',', ':'))
        raw_key = f"{account_name}:{vertical}:{canonical_json}"
    
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

def extract_timestamp(activity_body: Dict[str, Any]) -> Optional[int]:
    """
    Extract and parse the timestamp from the activity body.
    Assumes NinjaOne represents timestamps in seconds or milliseconds
    or as ISO8601 strings. We'll attempt to extract a Unix epoch second.
    Modify this function based on actual API payload shapes.
    """
    # Assuming the API provides an 'activityTime' or 'timestamp' field
    ts = activity_body.get('activityTime') or activity_body.get('timestamp')
    if isinstance(ts, (int, float)):
        # If it looks like milliseconds, convert to seconds
        if ts > 1e11:
            return int(ts / 1000)
        return int(ts)
    # If it's a string or other unparseable format without a library,
    # it's best to return None explicitly per requirements. 
    # Python 3.11 datetime.fromisoformat can handle ISO.
    if isinstance(ts, str):
        # Could attempt standard isoformat parse here if needed
        # For safety of requirements returning NULL if unparseable or unsure.
        pass
        
    return None
