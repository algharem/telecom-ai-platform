# Fix: ValueError: Out of range float values are not JSON compliant

## Error Analysis

The error occurred in `POST /api/v1/ml/train/from-logs` endpoint when returning the response:

```
ValueError: Out of range float values are not JSON compliant
```

### Root Causes

**1. NaN Values in JSON Response (FIXED)**
- When training on only 1 record, pandas `std()` returns `NaN`
- JSON cannot serialize `NaN`, `Inf`, or `-Inf` values
- Fixed by creating `_safe_float()` helper function that converts NaN/Inf to None

**2. Only 1 Record Being Loaded (REQUIRES INVESTIGATION)**
- Parser loaded only 1 gNB KPI record instead of aggregating all events
- Real log files contain ~1100 events but only 1 final KPI record generated
- Root issue: Cell ID extraction not working properly in log parser

## Fixes Applied

### Fix #1: NaN JSON Serialization (COMPLETED)

File: `api/v1/endpoints/prediction.py`

Created helper function:
```python
def _safe_float(value: float) -> float | None:
    """Convert float to JSON-safe value, handling NaN and Inf"""
    if value is None:
        return None
    if math.isnan(value):
        return None
    if math.isinf(value):
        return None
    return float(value)
```

Updated data_statistics response to use `_safe_float()` instead of `float()`:
```python
"data_statistics": {
    "prb_usage": {
        "mean": _safe_float(df['prb_usage'].mean()),  # Was: float()
        "std": _safe_float(df['prb_usage'].std()),    # Was: float()
        ...
    }
}
```

**Result**: Training endpoint now returns valid JSON even with 1 record

### Fix #2: Parser Debug Diagnostic (COMPLETED)

File: `scripts/diagnose_logs.py`

Created comprehensive diagnostic script that:
- Analyzes log file structure
- Identifies what patterns/fields are actually present
- Extracts sample cell IDs, IMSI values, and event types
- Shows distribution of different event types
- Helps identify why parser isn't extracting enough data

**Usage**:
```bash
python scripts/diagnose_logs.py /path/to/logs
```

## Next Steps Required

### 1. Run Diagnostic
```bash
python scripts/diagnose_logs.py open5gs/log
```

This will show:
- What cell IDs actually exist in logs
- What IMSI values are present
- Actual log line formats
- Which events are being detected

### 2. Update Parser Patterns
Based on diagnostic output, update the regex patterns in `parsers/open5gs_real_parser.py`:
- `_parse_amf_line()` - Cell ID extraction pattern
- `_parse_smf_line()` - Session event patterns
- `_parse_upf_line()` - Throughput extraction

### 3. Test Training Again
```bash
curl -X POST http://localhost:8000/api/v1/ml/train/from-logs
```

Expected behavior:
- Should return 200 OK with valid JSON
- `records_used` should be > 100 (not 1)
- All `data_statistics` values should be real numbers (no null values)

## Current Status

✅ **JSON Serialization Issue**: FIXED
- Training endpoint now handles NaN values properly
- Returns valid JSON response even with single record

⚠️ **Parser Data Loading**: REQUIRES DIAGNOSIS
- Only 1 KPI record generated from ~1100 log events
- Need to identify actual log format/structure
- Requires running diagnostic script to fix parser patterns

## Testing After Fix

```bash
# Test with current data
curl -X POST http://localhost:8000/api/v1/ml/train/from-logs

# Should return:
# {
#   "status": "success",
#   "records_used": 1,
#   "data_statistics": {
#     "prb_usage": {"mean": 23.0, "std": null, ...}  # std is null (not error)
#   }
# }
```

The JSON error is now fixed. The parser efficiency issue requires analyzing actual log format.
