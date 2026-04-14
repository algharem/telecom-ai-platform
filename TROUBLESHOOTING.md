# Troubleshooting Guide - API Test Issues

## Issue #1: Log Files Not Loading (CRITICAL)

### Symptoms
```
GET /api/v1/ml/data-source/status
{
  "available": false,
  "records_loaded": 0,
  "is_ready": false
}
```

### Root Cause
The configured log directory doesn't contain log files, or the path is incorrect.

### Solution

**Step 1: Check Configuration**
```bash
echo $LOG_BASE_PATH
# Expected output: /open5gs/log or /var/log/open5gs or your actual path
```

**Step 2: Verify Log Files Exist**
```bash
ls -la /open5gs/log/
# Should show: amf.log, smf.log, upf.log, nrf.log, mme.log, hss.log, ausf.log
```

**Step 3: If logs don't exist, copy them**
```bash
# Copy the test log files you provided
mkdir -p /open5gs/log
cp /path/to/your/logs/*.log /open5gs/log/
```

**Step 4: If directory is different, update path**
```bash
export LOG_BASE_PATH=/actual/path/to/logs
python app/main.py
```

**Step 5: Check logs in application startup**
Look for these logs when starting the API:
```
[STARTUP] Initializing data source: logs
[PARSER] Starting log parsing from: /open5gs/log
[PARSER] Found X .log files in /open5gs/log
[PARSER] Total events extracted: Y from Z files
[PROVIDER] Successfully loaded N KPI records from logs
```

---

## Issue #2: Empty KPI Records

### Symptoms
```
POST /api/v1/ml/kpi/batch/from-data-source?limit=10
{
  "records": [],
  "source": "logs",
  "count": 0
}
```

### Root Cause
Parser ran but extracted 0 events from logs (log format doesn't match parser patterns).

### Solution

**Check parser debug output:**
```bash
# Start app and check logs
python app/main.py 2>&1 | grep PARSER

# Look for:
# [PARSER] Pattern 'amf*.log': found X files
# [PARSER] Extracted Y events from amf.log
```

**If 0 events extracted:**
- Log format may not match parser regex patterns
- Check if logs have required fields (IMSI, session info, etc.)

**Verify log format:**
```bash
head -20 /open5gs/log/amf.log
# Should contain lines with timestamps, event types, IMSI, etc.
```

---

## Issue #3: Health Status "critical"

### Symptoms
```
GET /api/v1/monitoring/health
{
  "status": "critical",
  "records_processed": 0,
  "parse_success_rate": "0.0%"
}
```

### Root Cause
No records have been processed yet (logs not loaded = health is critical).

### Solution
Fix Issue #1 (logs not loading) - health will improve automatically once logs are processed.

---

## Issue #4: Missing Endpoints (404)

### Symptoms
```
GET /api/v1/monitoring/data-source/status → 404
GET /api/v1/monitoring/logs/status → 404
```

### Solution
FIXED - These endpoints have been added to `api/v1/endpoints/monitoring.py`:
- `GET /api/v1/monitoring/data-source/status`
- `GET /api/v1/monitoring/logs/status`

---

## Issue #5: Validation Errors in POST Requests

### Symptoms
```
POST /api/v1/ml/predict (No Body)
{
  "detail": [{"type": "missing", "msg": "Field required"}]
}
```

### Root Cause
Test script sends requests without valid bodies. These are **expected validation errors**, not bugs.

### Solution
This is normal behavior. Endpoints require proper request bodies:

**For /predict:**
```bash
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB-001",
    "metrics": {
      "prb_usage": 75,
      "throughput_mbps": 50,
      "latency_ms": 35,
      "packet_loss_percent": 0.5
    }
  }'
```

**For /train:**
```bash
curl -X POST http://localhost:8000/api/v1/ml/train \
  -H "Content-Type: application/json" \
  -d '{
    "duration_hours": 1,
    "anomaly_rate": 0.05
  }'
```

---

## Debugging Mode

Enable detailed logging to troubleshoot:

```bash
# Set debug logging
export DEBUG=true
python app/main.py 2>&1 | tee debug.log

# Search for specific issues
grep PARSER debug.log     # Parser activity
grep PROVIDER debug.log   # Data provider activity
grep ERROR debug.log      # All errors
grep STARTUP debug.log    # Startup sequence
```

---

## Environment Variables

```bash
# Data source selection
export DATA_SOURCE=logs          # Use log files (default)
export DATA_SOURCE=simulator     # Use simulator

# Log configuration
export LOG_BASE_PATH=/open5gs/log  # Where logs are

# Anomaly thresholds
export ANOMALY_PRB_THRESHOLD=90       # PRB usage %
export ANOMALY_LATENCY_THRESHOLD=50   # Latency ms
export ANOMALY_PACKET_LOSS_THRESHOLD=1  # Packet loss %

# API configuration
export API_HOST=0.0.0.0
export API_PORT=8000
export DEBUG=true
```

---

## Quick Checklist

- [ ] Log directory exists: `ls -la $LOG_BASE_PATH`
- [ ] Log files present: `ls -la $LOG_BASE_PATH/*.log`
- [ ] Correct path: `echo $LOG_BASE_PATH`
- [ ] API running: `curl http://localhost:8000/api/v1/monitoring/health`
- [ ] Logs being parsed: Check startup output for `[PARSER]` messages
- [ ] Data loaded: `curl http://localhost:8000/api/v1/ml/data-source/status`
