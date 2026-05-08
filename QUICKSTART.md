# Quick Start: Open5GS Log Parser Integration

## TL;DR - Get Running in 5 Minutes

### 1. Install Dependencies
```bash
cd /vercel/share/v0-project
pip install pyyaml  # For config file support
```

### 2. Run with Simulator (Default)
```bash
# Start the service (uses simulator by default)
python app/main.py

# In another terminal, test it
curl http://localhost:8000/api/v1/monitoring/health
```

You should see:
```json
{
  "status": "healthy",
  "uptime_seconds": 2.5,
  "records_processed": 0,
  "parse_success_rate": "100.0%"
}
```

### 3. Get KPI Data
```bash
# Fetch batch of KPI records with anomaly detection
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=10

# Response includes:
# - timestamp, gnb_id, metrics (prb, throughput, latency, packet_loss)
# - is_anomaly: true/false
# - anomaly_reason: why it was flagged
# - source: "simulator" or "logs"
```

### 4. Switch to Real Logs
```bash
# Set environment variable
export DATA_SOURCE=logs
export LOG_BASE_PATH=/var/log/open5gs

# Restart the service
python app/main.py
```

### 5. Monitor Pipeline
```bash
# Health check
curl http://localhost:8000/api/v1/monitoring/health

# Per-gNB statistics
curl http://localhost:8000/api/v1/monitoring/gnb/gNB_001

# Per-NF parsing stats
curl http://localhost:8000/api/v1/monitoring/nf/amf

# Anomaly detector stats
curl http://localhost:8000/api/v1/monitoring/detector-stats
```

## What Just Happened

The system:
1. Started with a configurable data provider (simulator or logs)
2. Generated/read KPI records
3. Applied pattern-based anomaly detection
4. Tracked metrics in the pipeline monitor
5. Exposed health and stats via REST API

## Key Files to Know

| File | Purpose |
|------|---------|
| `services/data_provider.py` | Switch between simulator and logs |
| `services/anomaly_detector.py` | Pattern-based anomaly detection |
| `services/pipeline_monitor.py` | Track pipeline health |
| `parsers/aggregators/gnb_aggregator.py` | Aggregate NF metrics to gNB level |
| `parsers/mappers/nf_to_gnb_mapper.py` | Map NF-specific metrics |
| `config/data_sources.yaml` | Configuration |
| `api/v1/endpoints/monitoring.py` | Health and stats endpoints |

## Architecture in 30 Seconds

```
┌─────────────────────────┐
│  Data Source            │
│  (Simulator or Logs)    │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│  Data Provider          │
│  (get_next_batch)       │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│  Anomaly Detector       │
│  (pattern-based rules)  │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│  Pipeline Monitor       │
│  (track health)         │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│  REST API Endpoints     │
│  (/monitoring/*)        │
└─────────────────────────┘
```

## Testing the Anomaly Detector

The detector uses these thresholds (configurable):

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| PRB Usage | > 90% | Network congestion |
| Latency | > 50ms | Service degradation |
| Packet Loss | > 1% | Transport issues |
| Throughput Drop | > 20% | Degradation |
| Registration Rate | < 95% | Authentication issues |

### Generate Test Data

```python
from services.kpi_simulator import TelecomKPISimulator

sim = TelecomKPISimulator()
df = sim.generate_training_data(hours=24, anomaly_rate=0.1)
print(df.head())

# You should see is_anomaly column with True/False and anomaly_type
```

### Run Detector on Test Data

```python
from services.anomaly_detector import AnomalyDetector
from services.data_provider import KPIRecord

detector = AnomalyDetector()

# Create sample record
record = KPIRecord(
    timestamp=datetime.now(),
    gnb_id="gNB_001",
    prb_usage=95.5,  # > 90 = anomaly!
    throughput=100.0,
    latency=25.0,
    packet_loss=0.1,
    source="test"
)

is_anomaly, reason = detector.detect(record)
print(f"Anomaly: {is_anomaly}, Reason: {reason}")
# Output: Anomaly: True, Reason: High PRB usage: 95.5% > 90%
```

## Switching Between Simulator and Logs

### Option 1: Environment Variable
```bash
# Use simulator (default)
export DATA_SOURCE=simulator
python app/main.py

# Use logs
export DATA_SOURCE=logs
export LOG_BASE_PATH=/var/log/open5gs
python app/main.py
```

### Option 2: Config File
Edit `config/data_sources.yaml`:
```yaml
data_source: "simulator"  # Change to "logs"
```

### Option 3: Code
```python
from services.data_provider import create_data_provider

# Simulator
provider = create_data_provider("simulator", {
    "base_stations": 10,
    "hours": 168
})

# Real logs
provider = create_data_provider("logs", {
    "base_path": "/var/log/open5gs",
    "watched_nfs": ["amf", "upf", "nrf", "ausf"]
})
```

## Troubleshooting

### Service Won't Start
```bash
# Check logs
python app/main.py 2>&1 | grep ERROR

# Verify dependencies
pip install -r requirements.txt
```

### No Records Being Processed
```bash
# Check data source availability
curl http://localhost:8000/api/v1/ml/data-source/status

# Check simulator is generating data
python -c "from services.kpi_simulator import TelecomKPISimulator; sim = TelecomKPISimulator(); df = sim.generate_training_data(hours=1); print(len(df))"
```

### High Anomaly Rate
- Thresholds might be too strict
- Edit `config/data_sources.yaml` or use env vars
- Example: `export ANOMALY_PRB_THRESHOLD=95`

## What's Next

1. **Train ML Model**: `POST /api/v1/ml/train` with SimulationConfig
2. **Real Predictions**: `POST /api/v1/ml/predict` with KPIMetrics
3. **Check NWDAF**: `/api/v1/nwdaf/analytics/request` for 3GPP compliance
4. **xApp Control**: `/api/v1/xapp/decisions` for O-RAN automation

## Key Endpoints

```bash
# Data source endpoints
GET  /api/v1/ml/data-source/status
GET  /api/v1/ml/logs/status
POST /api/v1/ml/kpi/batch/from-data-source

# Monitoring endpoints
GET  /api/v1/monitoring/health
GET  /api/v1/monitoring/stats
GET  /api/v1/monitoring/nf/{nf_type}
GET  /api/v1/monitoring/gnb/{gnb_id}
GET  /api/v1/monitoring/detector-stats
GET  /api/v1/monitoring/aggregator-stats

# Prediction endpoints (existing)
POST /api/v1/ml/predict
POST /api/v1/ml/train
POST /api/v1/ml/simulate/anomaly
```

## Need Help?

1. Read `IMPLEMENTATION_GUIDE.md` for detailed docs
2. Check `config/data_sources.yaml` for configuration
3. Review `services/pipeline_monitor.py` for metrics
4. Check monitoring endpoints for pipeline health

Good luck! 🚀
