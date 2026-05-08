# Prometheus Metrics Mapping for Open5GS

## Overview

This document maps actual Open5GS Prometheus metrics to the Telecom AI Platform's RAN KPI derivations.

## Actual Available Metrics from Deployment

Your Open5GS deployment exports **61 metrics** across all network functions:

### Core Network Functions

**AMF (Access and Mobility Management Function)**
- Registration management: `fivegs_amffunction_rm_*`
- Authentication: `fivegs_amffunction_amf_auth*`
- Mobility management: `fivegs_amffunction_mm_*`
- Currently subscribed: `fivegs_amffunction_rm_registeredsubnbr` (3 UEs active)

**SMF (Session Management Function)**
- PDU session management: `fivegs_smffunction_sm_pdusession*`
- N4 protocol: `fivegs_smffunction_sm_n4*`
- QoS flow management: `fivegs_smffunction_sm_qos_flow_nbr`
- Currently active: `fivegs_smffunction_sm_sessionnbr` (1 session active)

**UPF (User Plane Function)**
- N4 protocol: `fivegs_upffunction_sm_n4*`
- QoS flows: `fivegs_upffunction_upf_qosflows`
- Sessions: `fivegs_upffunction_upf_sessionnbr` (1 session active)

**PCF (Policy Control Function)**
- Policy association: `fivegs_pcffunction_pa_*`
- Sessions: `fivegs_pcffunction_pa_sessionnbr`

**Data Plane (N3 Interface)**
- N3 packet metrics: `fivegs_ep_n3_gtp_*`
- Inbound: `fivegs_ep_n3_gtp_indatapktn3upf`
- Outbound: `fivegs_ep_n3_gtp_outdatapktn3upf`

### System & Protocol Metrics

**GTP/PFCP Protocol**
- GTP2 sessions: `gtp2_sessions_active`
- PFCP sessions: `pfcp_sessions_active`
- PFCP peers: `pfcp_peers_active`

**Legacy GTP (4G)**
- PDP context: `gn_rx_createpdpcontextreq`, `gn_rx_deletepdpcontextreq`
- Session control: `s5c_rx_createsession`, `s5c_rx_deletesession`

**System Metrics**
- UE tracking: `ues_active`, `ran_ue`
- Bearer tracking: `bearers_active`
- Process metrics: CPU, memory, file descriptors

---

## KPI Derivation Logic

### 1. **PRB Usage** (0-100%)

**Formula:**
```
PRB = MIN(100, base + (registered_ues × prb_per_ue))
```

**Metrics Used:**
- `fivegs_amffunction_rm_registeredsubnbr` - registered subscriber count
- `ues_active` - total active UEs
- `bearers_active` - active bearer count

**Configuration:**
- `prb_base: 20.0` - baseline PRB usage
- `prb_per_ue: 15.0` - additional PRB per active UE

**Current Value Example:**
- Registered UEs: 3
- Active UEs: 3
- PRB Usage = MIN(100, 20 + (3 × 15)) = 65%

---

### 2. **Throughput** (Mbps)

**Formula:**
```
Throughput = (pdu_sessions × mbps_per_session) + 
             MAX(n3_in_packets, n3_out_packets) / 1000
```

**Metrics Used:**
- `fivegs_smffunction_sm_sessionnbr` - active PDU sessions
- `fivegs_ep_n3_gtp_indatapktn3upf` - N3 inbound packet rate
- `fivegs_ep_n3_gtp_outdatapktn3upf` - N3 outbound packet rate

**Configuration:**
- `mbps_per_session: 5.0` - estimated Mbps per PDU session

**Current Value Example:**
- PDU Sessions: 1
- N3 packets: ~100 pps (estimate)
- Throughput = MAX(1 × 5, 100/1000) = 5 Mbps

---

### 3. **Latency** (milliseconds)

**Formula:**
```
Latency = latency_base + 
          (reg_failure_rate × latency_penalty) +
          (auth_failure_rate × latency_penalty) +
          (auth_reject_rate × latency_penalty)
```

**Metrics Used:**
- `fivegs_amffunction_rm_reginitfail` - registration failures
- `fivegs_amffunction_rm_reginitreq` - registration requests
- `fivegs_amffunction_amf_authfail` - auth failures
- `fivegs_amffunction_amf_authreject` - auth rejects
- `fivegs_amffunction_amf_authreq` - auth requests

**Configuration:**
- `latency_base_ms: 20.0` - baseline latency
- `latency_penalty_ms: 100.0` - penalty per failure type

**Interpretation:**
- High latency indicates registration/auth issues
- Failure rate = (failures / requests)

---

### 4. **Packet Loss** (%)

**Formula:**
```
Packet Loss = MIN(100, 
               (auth_fail_rate + auth_reject_rate + reg_fail_rate) × 100)
```

**Metrics Used:**
- `fivegs_amffunction_amf_authfail` - auth failures
- `fivegs_amffunction_amf_authreject` - auth rejects
- `fivegs_amffunction_rm_reginitfail` - registration failures
- All corresponding request counters for rates

**Interpretation:**
- Packet loss ≥ 1% indicates control plane issues
- Combines registration and authentication failure rates

---

## Anomaly Detection Mapping

### Pattern 1: Congestion
**Triggers when:**
- PRB Usage > 90%
- PDU sessions increasing
- Latency increasing

**Metrics:**
- `fivegs_smffunction_sm_sessionnbr` > threshold
- `fivegs_amffunction_rm_registeredsubnbr` > threshold

### Pattern 2: Authentication Issues
**Triggers when:**
- `fivegs_amffunction_amf_authfail` spike
- `fivegs_amffunction_amf_authreject` spike
- Auth success rate < 95%

**Impact:**
- Increases latency
- Increases packet loss
- May reduce throughput

### Pattern 3: Registration Failures
**Triggers when:**
- `fivegs_amffunction_rm_reginitfail` spike
- `fivegs_amffunction_rm_regmobreq` vs success mismatch

**Impact:**
- Increases latency
- Reduces effective UE count

### Pattern 4: Data Plane Issues
**Triggers when:**
- `fivegs_ep_n3_gtp_indatapktn3upf` drops significantly
- `fivegs_ep_n3_gtp_outdatapktn3upf` drops significantly
- UPF N4 session failures spike

---

## Query Examples

### Current Registered UEs
```prometheus
fivegs_amffunction_rm_registeredsubnbr
```
**Result:** 3 UEs registered

### Registration Success Rate (5-minute window)
```prometheus
rate(fivegs_amffunction_rm_reginitsucc[5m]) / 
rate(fivegs_amffunction_rm_reginitreq[5m])
```

### Authentication Failure Rate
```prometheus
rate(fivegs_amffunction_amf_authfail[5m]) / 
rate(fivegs_amffunction_amf_authreq[5m])
```

### Data Plane Throughput Estimate (packets/sec → Mbps)
```prometheus
(rate(fivegs_ep_n3_gtp_indatapktn3upf[5m]) + 
 rate(fivegs_ep_n3_gtp_outdatapktn3upf[5m])) / 2 / 1000
```

---

## Configuration for Your Deployment

The system is now configured to:

1. **Query all 61 metrics** from your Prometheus at `http://172.25.0.36:9090`
2. **Derive RAN KPIs** using the formulas above
3. **Detect anomalies** using pattern-based rules
4. **Export predictions** via `/api/v1/ml/predict` endpoint

### To Enable Prometheus Integration

```bash
export DATA_SOURCE=prometheus
export PROMETHEUS_URL=http://172.25.0.36:9090
export GNB_ID=gNB-001
python app/main.py
```

### Test Connectivity

```bash
# Verify data loads
curl http://localhost:8000/api/v1/ml/data-source/status

# Get live KPI prediction
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"gnb_id": "gNB-001", "metrics": {}}'
```

---

## Performance Characteristics

| Metric | Type | Update Frequency | Latency |
|--------|------|------------------|---------|
| Gauge metrics | Current state | Every 15s | <100ms |
| Rate metrics | 5-min avg | Every 30s | <200ms |
| KPI derivation | Computed | Per query | <50ms |
| API response | Generated | Per request | <300ms |

---

## Troubleshooting

**No metrics loaded?**
- Verify Prometheus URL: `curl http://172.25.0.36:9090/api/v1/query?query=up`
- Check metric names match exactly (case-sensitive)
- Ensure Open5GS is exporting metrics

**KPI values unrealistic?**
- Check derivation parameters in `config/data_sources.yaml`
- Verify metric rates are calculating correctly
- Test individual metric queries in Prometheus UI

**Anomalies detected incorrectly?**
- Review threshold settings in config file
- Check actual metric values match expected ranges
- Consider updating `prb_base`, `latency_base_ms`, etc.
