# Real Open5GS Log Parsing

## Overview

The parsers can now extract data from actual Open5GS network function logs (AMF, SMF, UPF, NRF, HSS, AUSF) and convert them into gNB-level KPI metrics.

**Key Challenge Solved:** Open5GS logs don't contain direct gNB IDs or throughput metrics. These are core network logs (CN), not RAN logs. The solution is to:
1. Extract available session and event data from logs
2. Map cell IDs and IMSI information to gNB identifiers
3. Derive KPI metrics synthetically based on event patterns

## What Gets Extracted

### From Logs
- **Session Events**: Attach requests, session starts, session ends, authentication failures
- **IMSI**: Mobile subscriber identifiers (IMSI[001010000001004])
- **Cell IDs**: Radio cell identifiers (CellID[0x19b01]) from MME/eNB connections
- **APNs**: Access Point Names (internet, ims)
- **Timestamps**: When events occurred
- **Network Functions**: Which NF reported the event (AMF, SMF, UPF)

### Derived Metrics
Once events are aggregated by gNB:

| Metric | Derivation |
|--------|-----------|
| **gNB ID** | Mapped from cell_id (0x19b01 → gNB-001) |
| **PRB Usage** | Derived from session count (higher sessions = higher PRB) |
| **Throughput** | Estimated from successful sessions × 5 Mbps per session |
| **Latency** | Estimated from auth failures (each failure adds ~2ms) |
| **Packet Loss** | Calculated from failed_sessions / total_sessions |
| **Registration Success Rate** | (total - failed) / total * 100% |

## Data Flow

```
Open5GS Log Files
    ↓
[open5gs_real_parser.py]
    ↓
SessionEvent (parsed events with IMSI, cell_id, timestamp, type)
    ↓
[aggregate_to_gnb_kpi()]
    ↓
gNB-level metrics {prb_usage, throughput, latency, packet_loss}
    ↓
[LogFileDataProvider]
    ↓
API /logs/status, /kpi/batch/from-data-source
```

## Example: Parsing AMF Logs

### Raw Log Line
```
06/10 16:47:14.484: [mme] INFO:     ENB_UE_S1AP_ID[1] MME_UE_S1AP_ID[1] TAC[1] CellID[0x19b01]
06/10 16:47:14.484: [mme] INFO: [001010000001004] Unknown UE by IMSI
```

### Extracted
- **Event Type**: session_start (Attach request detected)
- **IMSI**: 001010000001004
- **Cell ID**: 0x19b01
- **Timestamp**: 2026-06-10 16:47:14.484
- **NF Type**: mme/amf

### Aggregated to gNB
```json
{
  "gnb_id": "gNB-001",
  "timestamp": "2026-03-30T13:45:00",
  "prb_usage": 35.2,
  "throughput": 25.0,
  "latency": 22.5,
  "packet_loss": 8.3,
  "registration_success_rate": 91.7
}
```

## Cell ID to gNB Mapping

Current mapping (in `Open5GSRealLogParser._build_cell_to_gnb_map()`):

```python
{
    '0x19b01': 'gNB-001',
    '0x19b02': 'gNB-002',
    '0x19b03': 'gNB-003',
    '0x19b04': 'gNB-004',
    '0x19b05': 'gNB-005',
}
```

**To customize:** Edit the mapping dictionary in `open5gs_real_parser.py` to match your actual cell IDs from logs.

## Supported Log Types

### AMF Logs
- **Extract**: Registration events, attachment requests, context releases
- **Patterns**: "Attach request", "Removed Session", "LOCATION-UPDATE-REJECT"
- **Fields**: IMSI, ENB_UE_S1AP_ID, MME_UE_S1AP_ID, CellID

### SMF Logs  
- **Extract**: Session lifecycle events, PDU session creation/removal
- **Patterns**: "Added] Number of SMF-UEs", "Removed Session"
- **Fields**: IMSI, APN, IPv4, IPv6

### UPF Logs
- **Extract**: Packet data events (if available)
- **Patterns**: Session create/remove events
- **Fields**: Limited in current implementation

### NRF Logs
- **Extract**: NF registration events (informational)
- **Patterns**: "NF registered", "Subscription created"

### HSS/AUSF Logs
- **Extract**: Authentication events (if available)
- **Patterns**: Authentication success/failure

## Usage

### 1. Configure Data Source
```bash
export DATA_SOURCE=logs
export LOG_BASE_PATH=/path/to/open5gs/logs
```

### 2. Run Parser
```python
from parsers.open5gs_real_parser import parse_open5gs_logs
from pathlib import Path

logs_dir = Path("/var/log/open5gs")
kpi_metrics = parse_open5gs_logs(logs_dir)

for metric in kpi_metrics:
    print(f"{metric['gnb_id']}: PRB={metric['prb_usage']}%, Latency={metric['latency']}ms")
```

### 3. API Integration
```bash
# Get logs status
curl http://localhost:8000/api/v1/monitoring/data-source/status

# Get logs status with gNB info
curl http://localhost:8000/api/v1/monitoring/logs/status

# Get next KPI batch from logs
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=10
```

## Limitations & Future Work

### Current Limitations
1. **gNB ID mapping**: Requires manual cell ID → gNB mapping
2. **Throughput synthetic**: Not actual throughput, estimated from session count
3. **No RAN metrics**: Core network logs lack direct radio metrics
4. **Time-based**: No continuous streaming, batch mode only

### Future Enhancements
1. **xRIC Integration**: Connect to xRIC for actual RAN metrics (PRB, SINR)
2. **Prometheus Integration**: Query Prometheus metrics endpoint for real metrics
3. **Flow Records**: Parse UPF flow records for actual throughput/latency
4. **ML Correlation**: Use ML to correlate CN events with RAN performance

## Debugging

### Enable detailed logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check parsed events
```python
from parsers.open5gs_real_parser import Open5GSRealLogParser
parser = Open5GSRealLogParser()
events = parser.process_file(Path("amf.log"), "amf")
for event in events[:5]:
    print(f"{event.timestamp} {event.event_type} {event.imsi} {event.cell_id}")
```

### Validate gNB mapping
```python
parser = Open5GSRealLogParser()
print(parser.cell_to_gnb_map)  # View current mappings
```

## Example: Processing Your Logs

```bash
# 1. Copy logs to project
cp /var/log/open5gs/*.log /vercel/share/v0-project/test_logs/

# 2. Parse and verify
python -c "
from parsers.open5gs_real_parser import parse_open5gs_logs
from pathlib import Path

logs = parse_open5gs_logs(Path('test_logs'))
print(f'Extracted {len(logs)} gNB metrics')
for m in logs[:3]:
    print(f'  {m[\"gnb_id\"]}: PRB={m[\"prb_usage\"]}%, Throughput={m[\"throughput\"]}Mbps')
"

# 3. Test API
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=5
```

## Questions?

The parser handles real Open5GS logs intelligently by:
- Extracting what's available (session events, IMSI, cell IDs)
- Mapping to standardized gNB identifiers
- Deriving reasonable KPI estimates from event patterns
- Maintaining backward compatibility with simulator data

If logs aren't being parsed, check:
1. File permissions and encoding
2. Log format matches Open5GS v2.6.3+ format
3. Cell ID mappings are correct for your deployment
4. Base path in configuration points to actual logs
