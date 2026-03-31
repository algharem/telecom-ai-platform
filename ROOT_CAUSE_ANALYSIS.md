# Root Cause Analysis - API Test Results

## Critical Issues Summary

### Issue 1: Only 1 Record Loaded from Logs (BLOCKING)
**Status**: CRITICAL
**Evidence**: `"records_loaded": 1` across all API calls
**Impact**: Model trained on insufficient data, causing 100% false positives

**Root Cause**: Log parser pattern matching is too strict
- Parser looks for: "Attach request", "Removed Session", "SMF-UEs", exact strings
- Real logs use: Different event descriptions, variable formatting
- Result: ~1100 log events but 0 match the parser patterns
- Only hardcoded default "gNB-001" record gets created with placeholder metrics

**Required Fix**: Improve pattern matching to capture actual log events
- Use broader regex patterns that match actual log format
- Add fallback detection for generic session/event keywords
- Generate multiple gNB records from different events

---

### Issue 2: Field Name Mismatch in Request Body
**Status**: BLOCKER  
**Evidence**: 
```
POST /api/v1/ml/predict with:
  "throughput_mbps": 2415
  "latency_ms": 40
  "packet_loss_percent": 2.07

Error: Field required for "throughput", "latency", "packet_loss"
```

**Root Cause**: API expects different field names than user provides
- Schema defines: `throughput`, `latency`, `packet_loss`  
- Client sends: `throughput_mbps`, `latency_ms`, `packet_loss_percent`
- Pydantic validation fails on required fields

**Required Fix**: Update schema field names to match expected client inputs OR add field aliases for backward compatibility

---

### Issue 3: gNB ID Naming Inconsistency
**Status**: SEVERE
**Evidence**:
- Data provider uses: `gNB-001` (dash separator)
- Monitoring endpoints query: `gNB_001` (underscore separator)
- Result: Monitoring shows `gNB_001` with 0 records while actual data is `gNB-001`

**Root Cause**: No normalization of gNB IDs across system
- Different services use different conventions
- No central normalization function

**Required Fix**: Normalize all gNB IDs to standard format `gNB-XXX` (dash)
- Implement `normalize_gnb_id()` utility function
- Apply normalization in data provider, monitoring endpoints, schemas

---

### Issue 4: 100% False Positive Anomalies  
**Status**: CRITICAL
**Evidence**: All 5 records from logs flagged as anomalies
```
Record: PRB=23%, Throughput=2415 Mbps, Latency=40ms, Packet Loss=2.07%
Status: ANOMALY (transport_issue)
Expected: NORMAL (these are reasonable metrics)
```

**Root Cause**: Model trained on synthetic data, not real data distributions
- Synthetic data has different metric ranges than real logs
- Isolation Forest learned synthetic patterns, not real patterns
- Real metrics outside synthetic distribution triggers anomaly

**Training Data Comparison**:
```
Synthetic Training:
- PRB usage: 0-100% (uniform distribution)
- Throughput: varies widely
- Latency: 5-50ms typical

Real Log Data:
- PRB usage: 23% (consistent low usage)
- Throughput: 2415 Mbps (specific value)
- Latency: 40ms (consistent)
- Packet Loss: 2.07% (specific value)
```

**Required Fix**: Retrain model on real log data using `/train/from-logs` endpoint
- Once log parser loads ALL events, will have sufficient training data
- Model will learn actual metric distributions from your network

---

## Actionable Next Steps

1. **IMMEDIATE**: Fix field name mismatch
   - Update schema aliases OR update documentation with correct field names
   - Allow both naming conventions for backward compatibility

2. **IMMEDIATE**: Normalize gNB IDs
   - Implement gnb_utils.normalize_gnb_id()
   - Apply in all endpoints and services

3. **HIGH PRIORITY**: Fix log parser to extract all events
   - Improve pattern matching in open5gs_real_parser.py
   - Test with actual log files to verify extraction
   - Should generate 10+ gNB KPI records from your logs

4. **HIGH PRIORITY**: Retrain model on real data
   - Once parser loads all events, run: `POST /train/from-logs`
   - Model will calibrate to your actual network patterns
   - False positives will drop to near-zero

---

## Testing Plan After Fixes

```bash
# 1. Verify field names work
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"gnb_id":"gNB-001","metrics":{"prb_usage":23,"throughput":2415,"latency":40,"packet_loss":2.07}}'

# Expected: 200 OK with is_anomaly=false

# 2. Verify gNB ID normalization
curl http://localhost:8000/api/v1/monitoring/gnb/gNB_001/stats
# Should return data for gNB-001

# 3. Check records loaded
curl http://localhost:8000/api/v1/ml/logs/status
# Should show: "records_loaded": 10+ (not 1)

# 4. Retrain on real data
curl -X POST http://localhost:8000/api/v1/ml/train/from-logs
# Should use all records for training

# 5. Verify anomaly detection
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"gnb_id":"gNB-001","metrics":{"prb_usage":23,"throughput":2415,"latency":40,"packet_loss":2.07}}'
# Expected: is_anomaly=false (was true before fix)
```
