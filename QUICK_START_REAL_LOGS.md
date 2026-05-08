# Quick Start: Real Log Parsing

## TL;DR - Get Logs Running in 5 Minutes

### 1. Copy Your Logs
```bash
cp amf.log smf.log upf.log nrf.log /var/log/open5gs/
```

### 2. Set Environment
```bash
export DATA_SOURCE=logs
export LOG_BASE_PATH=/var/log/open5gs
```

### 3. Run Application
```bash
python app/main.py
```

### 4. Test It Works
```bash
# Check logs are loaded
curl http://localhost:8000/api/v1/monitoring/logs/status

# Get KPI batch from logs
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=5

# Make predictions
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB-001",
    "timestamp": "2023-06-10T16:47:00Z",
    "metrics": {
      "prb_usage": 35.2,
      "throughput_mbps": 25.0,
      "latency_ms": 22.5,
      "packet_loss_percent": 8.3
    }
  }'
```

## What Changed?

| Before | After |
|--------|-------|
| ❌ Can't parse real logs | ✅ Parses Open5GS logs |
| ❌ No gNB ID in logs | ✅ Maps cell_id → gNB |
| ❌ No throughput data | ✅ Derives from sessions |
| ❌ Simulator only | ✅ Logs OR simulator |

## What Gets Parsed

Your logs contain:
```
Session Events (Attach, Release, Auth Failures)
    ↓
Cell IDs (0x19b01 from CellID[0xXXXXX])
    ↓
IMSI (user IDs like 001010000001004)
    ↓
Timestamps (when events happened)
```

Parser converts to:
```
gNB Metrics:
  - gNB ID (from cell_id mapping)
  - PRB Usage % (from session count)
  - Throughput Mbps (from successful sessions)
  - Latency ms (from auth retries)
  - Packet Loss % (from failed sessions)
```

## Supported Log Files

Parser automatically finds and processes:
- `amf.log` - Access/mobility events
- `smf.log` - PDU session management  
- `upf.log` - User plane (if available)
- `nrf.log` - NF registration (optional)
- `mme.log` - 4G equivalent of AMF
- `hss.log`, `ausf.log` - Auth logs (if present)

## Configuration

### Basic Setup
```bash
DATA_SOURCE=logs                    # Use logs instead of simulator
LOG_BASE_PATH=/var/log/open5gs      # Where your logs are
```

### Optional (Advanced)
```bash
ANOMALY_PRB_THRESHOLD=90            # Alert if PRB > 90%
ANOMALY_LATENCY_THRESHOLD=50        # Alert if latency > 50ms
ANOMALY_PACKET_LOSS_THRESHOLD=1     # Alert if packet_loss > 1%
```

## Customize Cell ID Mapping

If your cell IDs don't match default mapping:

1. Find your cell IDs:
```bash
grep -o "CellID\[[^]]*\]" amf.log | sort -u
```

2. Edit `parsers/open5gs_real_parser.py`:
```python
def _build_cell_to_gnb_map(self) -> Dict[str, str]:
    return {
        '0x19b01': 'gNB-001',      # Change this
        '0x12345': 'gNB-SiteA',    # Add your mapping
        '0xABCDE': 'gNB-SiteB',
    }
```

3. Restart application

## Troubleshoot

### Logs not loading?
```bash
# 1. Check file exists
ls -la /var/log/open5gs/amf.log

# 2. Check permissions
chmod 644 /var/log/open5gs/*.log

# 3. Test parser
python scripts/test_real_logs.py
```

### No gNB-001 found?
Your cell IDs don't match mapping. Find actual IDs:
```bash
grep "CellID\[" amf.log | head -1
```

Update mapping in `open5gs_real_parser.py`

### Metrics look wrong?
Run diagnostic:
```bash
python scripts/test_real_logs.py
```

Check session counts - if very low, metrics will be low too.

## API Endpoints

### Get Status
```bash
curl http://localhost:8000/api/v1/monitoring/logs/status
```

### Get KPI Batch
```bash
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=10
```

### Make Prediction
```bash
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB-001",
    "metrics": {
      "prb_usage": 35.2,
      "throughput_mbps": 25.0,
      "latency_ms": 22.5,
      "packet_loss_percent": 8.3
    }
  }'
```

### Train Model (Optional)
```bash
curl -X POST http://localhost:8000/api/v1/ml/train
```

## Key Files

- **Parser**: `parsers/open5gs_real_parser.py`
- **Provider**: `services/data_provider.py` (LogFileDataProvider)
- **Tests**: `scripts/test_real_logs.py`
- **Docs**: `REAL_LOGS_PARSING.md` (detailed guide)

## Next Steps

1. ✅ Copy logs to `/var/log/open5gs/`
2. ✅ Set `DATA_SOURCE=logs`
3. ✅ Run `python app/main.py`
4. ✅ Call `/ml/kpi/batch/from-data-source`
5. ✅ Use predictions for monitoring/alerting

Done! Your real logs are now powering the AI model.

For more details, see `REAL_LOGS_PARSING.md`
