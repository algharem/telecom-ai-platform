# Data Source Configuration Fix

## Problem Found
When running with `export DATA_SOURCE=simulator`, the API still showed:
```json
{
  "available": false,
  "source_info": {
    "type": "logs",
    "records_loaded": 0,
    "is_ready": false
  }
}
```

## Root Cause
In `app/main.py:99`, the startup event was calling:
```python
provider_config = get_provider_config(data_source)
```

This was NOT passing environment variables, so `get_provider_config()` had no access to them. The function always used defaults, and since no env dict was passed, it defaulted to using hardcoded paths for logs.

## Fix Applied
Updated the startup event to pass environment variables to the config function:
```python
provider_config = get_provider_config(data_source, dict(os.environ))
```

Now the system can read:
- `DATA_SOURCE=simulator` or `DATA_SOURCE=logs`
- `LOG_BASE_PATH=/path/to/logs`
- `SIMULATOR_BASE_STATIONS=10`
- `SIMULATOR_HOURS=168`
- `SIMULATOR_ANOMALY_RATE=0.05`

## How to Use

### Option 1: Use Simulator (Testing)
```bash
export DATA_SOURCE=simulator
export SIMULATOR_BASE_STATIONS=10
python app/main.py
```

Expected response:
```json
{
  "available": true,
  "source_info": {
    "type": "simulator",
    "base_stations": 10,
    "total_records": 10080,
    "current_position": 0
  }
}
```

### Option 2: Use Real Logs
```bash
export DATA_SOURCE=logs
export LOG_BASE_PATH=/var/log/open5gs
python app/main.py
```

Expected response:
```json
{
  "available": true,
  "source_info": {
    "type": "logs",
    "base_path": "/var/log/open5gs",
    "records_loaded": 1234,
    "is_ready": true
  }
}
```

## Verification

After fix, test:
```bash
curl http://localhost:8000/api/v1/ml/data-source/status
```

Should show:
- `"available": true`
- `"type": "simulator"` or `"type": "logs"` (based on DATA_SOURCE setting)
- Non-zero records_loaded for simulator
