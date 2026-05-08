# Predict Endpoint - Auto-Fetch Guide

## Overview
The `/api/v1/ml/predict` endpoint now supports **auto-fetching metrics** from your configured data source (Prometheus, simulator, or logs) when metrics are not provided or are incomplete.

## Usage Examples

### Option 1: Auto-Fetch All Metrics (Recommended)
Omit metrics entirely or pass empty metrics object. The endpoint will fetch from your data provider.

```bash
# Completely omit metrics
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"gnb_id": "gNB-001"}'

# Or pass empty metrics object
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"gnb_id": "gNB-001", "metrics": {}}'
```

### Option 2: Partial Metrics (Auto-Fill Missing Values)
Provide some metrics, and missing ones are fetched from data provider.

```bash
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB-001",
    "metrics": {
      "prb_usage": 45.5
    }
  }'
# throughput, latency, packet_loss will be auto-fetched
```

### Option 3: Explicit Metrics
Provide all metrics explicitly.

```bash
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB-001",
    "metrics": {
      "prb_usage": 45.5,
      "throughput": 500.0,
      "latency": 25.0,
      "packet_loss": 0.5
    }
  }'
```

## Response
All three options return the same response format with anomaly prediction:

```json
{
  "prediction_id": "uuid",
  "gnb_id": "gNB-001",
  "timestamp": "2026-03-31T15:30:00.000000",
  "metrics": {
    "prb_usage": 45.5,
    "throughput": 500.0,
    "latency": 25.0,
    "packet_loss": 0.5
  },
  "result": {
    "is_anomaly": false,
    "anomaly_score": 0.2,
    "explanation": "No anomalies detected"
  },
  "processing_time_ms": 12.5
}
```

## Configuration
The data source to fetch from is determined by `DATA_SOURCE` environment variable:
- `prometheus` - Fetch from Prometheus (real-time metrics)
- `simulator` - Fetch from synthetic data generator
- `logs` - Parse from Open5GS log files

Set via:
```bash
export DATA_SOURCE=prometheus
export PROMETHEUS_URL=http://172.25.0.36:9090
python app/main.py
```

## Metrics Field Mappings
All of these field names are accepted (with or without suffixes):
- `prb_usage` or `prb_usage`
- `throughput` or `throughput_mbps`
- `latency` or `latency_ms`
- `packet_loss` or `packet_loss_percent`
