# Prometheus Integration Setup

## Overview

The Telecom AI Platform now supports real-time metrics from Prometheus. This enables live monitoring of Open5GS deployments without file-based log parsing.

## Quick Start

### 1. Enable Prometheus Data Source

```bash
export DATA_SOURCE=prometheus
export PROMETHEUS_URL=http://172.25.0.36:9090
export GNB_ID=gNB-001

python app/main.py
```

### 2. Verify Connection

```bash
curl http://localhost:8000/api/v1/ml/data-source/status
```

Expected response:
```json
{
  "timestamp": "2026-03-31T15:00:00.123456",
  "available": true,
  "source_info": {
    "type": "prometheus",
    "url": "http://172.25.0.36:9090",
    "gnb_id": "gNB-001",
    "is_ready": true,
    "gauge_metrics": [
      "fivegs_amffunction_rm_registeredsubnbr",
      "fivegs_smffunction_sm_sessionnbr",
      ...
    ]
  }
}
```

### 3. Get KPI Data

```bash
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=1
```

Response includes real-time KPI metrics derived from Prometheus.

## Configuration

### Environment Variables

```bash
# Data source selection
DATA_SOURCE=prometheus

# Prometheus connection
PROMETHEUS_URL=http://172.25.0.36:9090

# gNB identification
GNB_ID=gNB-001

# KPI Derivation Parameters (optional)
PRB_BASE=20.0              # Base PRB usage %
PRB_PER_UE=15.0           # PRB % per registered UE
MBPS_PER_SESSION=5.0      # Throughput per PDU session
LATENCY_BASE_MS=20.0      # Base latency
LATENCY_PENALTY_MS=100.0  # Latency penalty per failure unit
```

### Configuration File

Edit `config/data_sources.yaml`:

```yaml
data_source: "prometheus"

prometheus:
  enabled: true
  url: "http://172.25.0.36:9090"
  gnb_id: "gNB-001"
  
  derivation:
    prb_base: 20.0
    prb_per_ue: 15.0
    mbps_per_session: 5.0
    latency_base_ms: 20.0
    latency_penalty_ms: 100.0
```

## Metrics

### Gauge Metrics (Current Values)

| Metric | Description | Maps To |
|--------|-------------|---------|
| `fivegs_amffunction_rm_registeredsubnbr` | Registered UEs | `registered_ues` |
| `fivegs_smffunction_sm_sessionnbr` | PDU Sessions | `pdu_sessions` |
| `fivegs_upffunction_upf_sessionnbr` | UPF Sessions | `upf_sessions` |
| `fivegs_smffunction_sm_qos_flow_nbr` | QoS Flows | `qos_flows` |

### Rate Metrics (5-minute Rate)

| Metric | Description | Maps To |
|--------|-------------|---------|
| `fivegs_ep_n3_gtp_indatapktn3upf[5m]` | N3 In Packet Rate | `n3_in_packets` |
| `fivegs_ep_n3_gtp_outdatapktn3upf[5m]` | N3 Out Packet Rate | `n3_out_packets` |
| `fivegs_amffunction_amf_authfail[5m]` | Auth Failure Rate | `auth_fails` |
| `fivegs_amffunction_amf_authreq[5m]` | Auth Request Rate | `auth_requests` |
| `fivegs_amffunction_rm_reginitsucc[5m]` | Registration Success Rate | `reg_success` |

## KPI Derivation

The system derives RAN-level KPIs from core network metrics using these formulas:

### PRB Usage
```
prb_usage = min(100, base_prb + registered_ues * prb_per_ue)
```
- Default: 20% base + 15% per UE
- Example: 5 UEs → 20 + 5*15 = 95% PRB

### Throughput
```
throughput = pdu_sessions * mbps_per_session
```
- Default: 5 Mbps per session
- Example: 8 sessions → 40 Mbps

### Latency
```
auth_fail_rate = auth_fails / auth_requests
latency = min(100, base_latency + auth_fail_rate * penalty)
```
- Default: 20ms base + 100ms penalty per failure rate
- Example: 2% failure → 20 + 0.02*100 = 22ms

### Packet Loss
```
packet_loss = min(100, auth_fail_rate * 100)
```
- Direct correlation to auth failure rate

## Testing

Run the integration test suite:

```bash
python scripts/test_prometheus_integration.py
```

This tests:
1. Prometheus connectivity
2. Open5GS metrics availability
3. Individual metric queries
4. Rate metric queries
5. KPI derivation logic
6. Full provider integration

## Architecture

```
Prometheus (http://172.25.0.36:9090)
    ↓
PrometheusClient (prometheus_client.py)
    - Query gauge metrics (instant)
    - Query rate metrics (5m average)
    - Health checks
    ↓
PrometheusDataProvider (data_provider.py)
    - Fetch metrics
    - Derive RAN KPIs
    - Return KPIRecord
    ↓
AI Model Pipeline
    - Anomaly detection
    - Prediction
    - Monitoring
```

## Fallback Strategy

If Prometheus is unavailable, automatically fall back to logs:

```bash
export DATA_SOURCE=prometheus
export FALLBACK_TO_LOGS=true
export LOG_BASE_PATH=/var/log/open5gs

python app/main.py
```

## Performance

- **Query Latency**: <100ms per metric (typical)
- **Records per Batch**: 1 (snapshot) or multiple (time range query)
- **Update Frequency**: 5-10 seconds (Prometheus scrape interval)
- **Throughput**: ~10,000 KPI records/hour for continuous queries

## Troubleshooting

### Prometheus Not Available

```bash
curl http://172.25.0.36:9090/-/healthy
```

Should return HTTP 200 if Prometheus is running.

### Open5GS Metrics Not Found

Check Prometheus UI: http://172.25.0.36:9090/graph

Search for: `fivegs_amffunction_rm_registeredsubnbr`

### Wrong KPI Values

Check derivation parameters in config. Adjust `prb_base`, `prb_per_ue`, etc. to match your network.

## Next Steps

1. Train ML model on Prometheus data: `POST /api/v1/ml/train/from-logs`
2. Run predictions: `POST /api/v1/ml/predict`
3. Monitor with xApp: `GET /api/v1/xapp/decisions`

## References

- Prometheus Documentation: https://prometheus.io/docs/
- Open5GS: https://open5gs.org/
- PromQL: https://prometheus.io/docs/prometheus/latest/querying/basics/
