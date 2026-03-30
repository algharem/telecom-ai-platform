# Open5GS Log Parser Integration - Implementation Guide

## Overview

This document describes the complete implementation of Open5GS log parsing and integration into the telecom AI platform. The system replaces the KPI simulator with real network function logs while maintaining backward compatibility with the simulator mode.

## Architecture

### Data Flow

```
Open5GS Logs (AMF, UPF, NRF, AUSF)
    ↓
[LogFileDataProvider]
    ↓
[gNB Metrics Aggregator] (1-minute windows)
    ↓
[NF-to-gNB Mappers] (converts NF metrics to gNB KPIs)
    ↓
[KPI Records] (unified format)
    ↓
[Anomaly Detector] (pattern-based thresholds)
    ↓
[API Endpoints / ML Model]
```

### Components

#### Phase 1: Data Source Abstraction Layer
**Files:**
- `services/data_provider.py` - Abstract DataProvider interface with SimulatorDataProvider and LogFileDataProvider
- `config/data_sources.yaml` - Configuration for switching between data sources

**Key Classes:**
- `DataProvider` - Abstract base class defining interface
- `SimulatorDataProvider` - Wraps existing KPI simulator
- `LogFileDataProvider` - Reads real Open5GS logs (Phase 2 integration)
- `KPIRecord` - Unified KPI data structure from any source

**Usage:**
```python
from services.data_provider import create_data_provider

# Create provider (simulator or logs)
provider = create_data_provider("simulator", config)
batch = provider.get_next_batch(limit=100)

# Check availability
if provider.is_available():
    info = provider.get_source_info()
```

#### Phase 2: Log Parsing & Aggregation Engine
**Files:**
- `parsers/aggregators/gnb_aggregator.py` - Aggregates NF metrics into gNB-level KPIs
- `parsers/mappers/nf_to_gnb_mapper.py` - Maps NF-specific metrics to gNB metrics

**Key Classes:**
- `GnBMetricsAggregator` - Maintains 1-minute sliding windows per gNB
- `WindowMetrics` - Metrics for a single aggregation window
- `NFMetricsMapper` - Base class for NF mappers
- `AMFMetricsMapper` - Maps AMF registration/auth metrics
- `UPFMetricsMapper` - Maps throughput/latency/packet loss
- `NRFMetricsMapper` - Maps service availability
- `AUSFMetricsMapper` - Maps authentication metrics

**Key Methods:**
```python
aggregator = GnBMetricsAggregator(window_seconds=60)

# Add metrics from parsed logs
aggregator.add_nf_metric(
    gnb_id="gNB_001",
    nf_type="amf",
    metric_name="registration_latency",
    value=45.2,
    timestamp=datetime.now()
)

# Get completed windows
completed = aggregator.get_completed_windows()

# Flush on shutdown
all_windows = aggregator.flush()
```

#### Phase 3: Anomaly Detection with Thresholds
**Files:**
- `services/anomaly_detector.py` - Pattern-based anomaly detection

**Key Classes:**
- `AnomalyDetector` - Detects anomalies using configurable thresholds
- `AnomalyThresholds` - Threshold configuration
- `AnomalyAggregator` - Tracks anomalies over time

**Detection Patterns:**
- **Congestion**: PRB usage > 90%
- **Latency Issues**: Latency > 50ms
- **Packet Loss**: Packet loss > 1%
- **Throughput Degradation**: Throughput drop > 20% from baseline
- **Registration Issues**: Success rate < 95%

**Usage:**
```python
detector = AnomalyDetector({
    "prb_usage_percent": 90,
    "latency_ms": 50,
    "packet_loss_percent": 1
})

# Detect single record
is_anomaly, reason = detector.detect(kpi_record)

# Batch detection
results = detector.detect_batch(records)

# Get stats
stats = detector.get_stats()
```

#### Phase 4: Data Flow Integration
**Files:**
- `app/main.py` - Startup/shutdown initialization of services
- `api/v1/endpoints/prediction.py` - New data source endpoints

**New Endpoints:**
```
GET  /api/v1/ml/data-source/status      - Get current data source
GET  /api/v1/ml/logs/status             - Get log processing status
POST /api/v1/ml/kpi/batch/from-data-source - Fetch KPI batch with anomalies
```

**Startup Initialization:**
```python
@app.on_event("startup")
async def startup_event():
    # Initialize data provider
    app.data_provider = create_data_provider(data_source, config)
    
    # Initialize anomaly detector
    app.anomaly_detector = AnomalyDetector(thresholds)
    
    # Initialize monitoring
    app.pipeline_monitor = PipelineMonitor()
    
    # Initialize aggregator for log processing
    app.gnb_aggregator = GnBMetricsAggregator()
```

#### Phase 5: Monitoring & Observability
**Files:**
- `services/pipeline_monitor.py` - Track pipeline health and performance
- `api/v1/endpoints/monitoring.py` - Monitoring endpoints

**Key Classes:**
- `PipelineMonitor` - Central monitoring hub
- `ParseMetrics` - Metrics for parsing session
- `AnomalyMetrics` - Metrics for anomaly window

**Monitoring Endpoints:**
```
GET /api/v1/monitoring/health           - Overall health status
GET /api/v1/monitoring/stats            - Comprehensive statistics
GET /api/v1/monitoring/nf/{nf_type}     - Per-NF stats (amf, upf, etc.)
GET /api/v1/monitoring/gnb/{gnb_id}     - Per-gNB stats
GET /api/v1/monitoring/data-source      - Data source status
GET /api/v1/monitoring/parse-rate       - Parse rate per minute
GET /api/v1/monitoring/anomaly-rates    - Anomaly rates per gNB
GET /api/v1/monitoring/detector-stats   - Detector statistics
GET /api/v1/monitoring/aggregator-stats - Aggregator statistics
```

## Configuration

### YAML Configuration (config/data_sources.yaml)

```yaml
# Active data source: "simulator" or "logs"
data_source: "simulator"

# Simulator configuration
simulator:
  enabled: true
  base_stations: 10
  hours: 168
  anomaly_rate: 0.05

# Log file configuration
logs:
  enabled: false
  base_path: "/var/log/open5gs"
  watched_nfs: ["amf", "upf", "nrf", "ausf"]
  polling_interval_seconds: 5

# Anomaly thresholds
anomaly_detection:
  thresholds:
    prb_usage_percent: 90
    latency_ms: 50
    packet_loss_percent: 1
```

### Environment Variables

```bash
# Data source selection
DATA_SOURCE=simulator  # or "logs"

# Simulator configuration
SIMULATOR_BASE_STATIONS=10
SIMULATOR_RANDOM_SEED=42
SIMULATOR_HOURS=168
SIMULATOR_ANOMALY_RATE=0.05

# Log configuration
LOG_BASE_PATH=/var/log/open5gs
LOG_WATCHED_NFS=amf,upf,nrf,ausf
LOG_POLLING_INTERVAL=5

# Anomaly thresholds
ANOMALY_PRB_THRESHOLD=90
ANOMALY_LATENCY_THRESHOLD=50
ANOMALY_PACKET_LOSS_THRESHOLD=1
```

## Integration Steps

### Step 1: Verify Imports
All files properly import required dependencies. Check:
- `services/data_provider.py` imports `TelecomKPISimulator`
- `app/main.py` imports all services
- `api/v1/endpoints/monitoring.py` has proper Request import

### Step 2: Enable Monitoring
In your API initialization, monitoring is automatically started:
```python
app.pipeline_monitor = PipelineMonitor(retention_minutes=60)
```

### Step 3: Use Data Provider
Switch between simulator and logs at runtime:
```python
# Via environment variable
export DATA_SOURCE=logs
export LOG_BASE_PATH=/var/log/open5gs

# Via code
provider = create_data_provider("logs", {
    "base_path": "/var/log/open5gs",
    "watched_nfs": ["amf", "upf", "nrf", "ausf"]
})
```

### Step 4: Check Health
Monitor pipeline health via endpoints:
```bash
curl http://localhost:8000/api/v1/monitoring/health
curl http://localhost:8000/api/v1/monitoring/stats
```

## Testing

### Test Simulator Mode
```python
from services.data_provider import create_data_provider

# Create simulator
provider = create_data_provider("simulator", {
    "base_stations": 5,
    "hours": 24,
    "anomaly_rate": 0.1
})

# Fetch batch
batch = provider.get_next_batch(100)
print(f"Got {len(batch)} records")

# Use with detector
from services.anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
results = detector.detect_batch(batch)
```

### Test Aggregation
```python
from parsers.aggregators.gnb_aggregator import GnBMetricsAggregator
from datetime import datetime

aggregator = GnBMetricsAggregator(window_seconds=60)

# Add metrics
for i in range(100):
    aggregator.add_nf_metric(
        gnb_id="gNB_001",
        nf_type="amf",
        metric_name="registration_latency",
        value=40 + (i % 20),
        timestamp=datetime.now()
    )

# Get results
completed = aggregator.get_completed_windows()
print(f"Completed windows: {len(completed)}")
```

### Test Full Pipeline
```bash
# Check data source
curl http://localhost:8000/api/v1/ml/data-source/status

# Get KPI batch
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=50

# Check health
curl http://localhost:8000/api/v1/monitoring/health

# Get anomaly stats
curl http://localhost:8000/api/v1/monitoring/detector-stats
```

## Migration from Simulator to Real Logs

### Phase 1: Parallel Running
Keep simulator as fallback while logs are being configured:
```bash
DATA_SOURCE=simulator  # Current mode
```

### Phase 2: Enable Log Monitoring
```bash
DATA_SOURCE=logs
LOG_BASE_PATH=/var/log/open5gs
```

### Phase 3: Validate Data Quality
Check monitoring endpoints:
- `/monitoring/health` - Parse success rate
- `/monitoring/nf/{nf_type}` - Per-NF metrics
- `/monitoring/data-source` - Log file status

### Phase 4: Switch Training
Update model training to use real logs:
```python
provider = create_data_provider("logs", log_config)
batch = provider.get_next_batch(limit=10000)

# Train on real data
detector.train(batch)
```

## Troubleshooting

### Data Source Not Available
```
Issue: "Data provider not initialized"
Solution: Check app.on_event("startup") is properly decorating startup function
```

### Missing gNB IDs in Logs
```
Issue: Parser can't extract gNB IDs from log messages
Solution: Check NF mapper regex patterns match your log format
Example: GNBID_PATTERN = re.compile(r'gNB[_-]?(\d{3,5})')
```

### Low Parse Success Rate
```
Issue: High parse_errors in monitoring stats
Solution:
1. Check log format matches Open5GS standard
2. Verify NF type matches configured watched_nfs
3. Check character encoding (UTF-8 required)
4. Review detailed error logs
```

### Anomaly Detection Too Sensitive
```
Issue: Too many false positives
Solution: Update thresholds in config/data_sources.yaml
- Increase PRB threshold: 90 → 95
- Increase latency threshold: 50ms → 100ms
- Decrease sensitivity via ANOMALY_* env vars
```

## Performance Considerations

### Window Size
- Default: 60 seconds (1 minute)
- Smaller windows: More granular detection, higher CPU
- Larger windows: Lower resolution, better averaging

### Buffer Management
- `max_buffer_size: 10000` - Prevent OOM on high-volume logs
- `flush_interval_seconds: 30` - Timely delivery of windows

### Data Freshness
- Monitor `data_freshness_seconds` metric
- Target: < 5 seconds lag between log time and processing
- If > 30 seconds: Logs are backing up, increase parse rate

### Monitoring Retention
- Default: 60 minutes of metrics kept in memory
- Adjust `retention_minutes` for longer history
- For permanent storage, export to time-series DB

## Future Enhancements

1. **Persistent Storage**: Export windows to PostgreSQL/InfluxDB
2. **Real-time Streaming**: Kafka or Redis integration for live logs
3. **Advanced ML**: Replace thresholds with trained isolation forest
4. **Cross-gNB Analytics**: Correlate anomalies across base stations
5. **Historical Analysis**: Backfill training data from log archives
6. **Distributed Processing**: Scale to multiple parser instances

## References

- Open5GS Documentation: https://open5gs.org/
- 3GPP TS 28.552: 5G Performance Measurements
- 3GPP TS 29.520: NWDAF Services
- O-RAN RIC Architecture: https://www.o-ran.org/

## Support

For questions or issues:
1. Check monitoring endpoints for pipeline health
2. Review logs with `log_level: DEBUG` in data_sources.yaml
3. Validate log format against Open5GS standards
4. Test with simulator mode first before switching to logs
