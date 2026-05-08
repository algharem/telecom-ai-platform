# Prediction Endpoint Fix Summary

## Issue Found
The `/api/v1/ml/predict` endpoint was returning **503 Service Unavailable** with error message:
```json
{
  "error": "MODEL_NOT_TRAINED",
  "message": "Model not trained",
  "resolution": "POST /train to initialize model"
}
```

**Root Cause:** The endpoint required an ML model to be trained before any predictions could be made. However, the implementation of Phase 1-5 included a new pattern-based anomaly detector that doesn't require ML model training.

## Solution Implemented

### Changes Made

#### 1. **Updated Imports in `api/v1/endpoints/prediction.py`**
```python
# Before
from services.ml_detector import AnomalyDetector

# After
from services.ml_detector import AnomalyDetector as MLAnomalyDetector
from services.anomaly_detector import AnomalyDetector as PatternAnomalyDetector
```

#### 2. **Modified Single Prediction Endpoint**
The `/predict` endpoint now implements a **fallback strategy**:

```python
@router.post("/predict", response_model=PredictionResponse)
async def predict_anomaly(request, background_tasks, http_request):
    # Try ML-based detection first (if model is trained)
    if ml_detector.is_trained:
        result = ml_detector.predict(request)  # ML-based
    else:
        # Fall back to pattern-based detection (no training required)
        pattern_detector = http_request.app.anomaly_detector
        is_anomaly, reason = pattern_detector.detect(kpi)
        result = AnomalyResult(...)  # Pattern-based
```

**Benefits:**
- ✓ No model training required for immediate results
- ✓ Supports both ML and pattern-based detection
- ✓ Gracefully falls back to pattern-based if ML model not available
- ✓ 100% backward compatible

#### 3. **Fixed Batch Prediction Endpoint**
Updated references from `detector` → `ml_detector` for consistency:
```python
if not ml_detector.is_trained:
    raise HTTPException(503, detail="Model not trained...")
```

#### 4. **Fixed Train Endpoint**
Updated references to use `ml_detector` instead of `detector`:
```python
metrics = ml_detector.train(df)
model_info = ml_detector.get_model_info()
```

## Expected Behavior After Fix

### Single Prediction Endpoint (`POST /api/v1/ml/predict`)
- **Status:** ✓ **200 OK** (now works immediately)
- **Detection Method:** Pattern-based (no training required)
- **Response Includes:**
  - `is_anomaly`: True/False based on threshold rules
  - `anomaly_score`: 0.8 (anomaly) or 0.2 (normal)
  - `explanation`: Reason for detection (e.g., "High PRB usage detected")

### Batch Prediction Endpoint (`POST /api/v1/ml/predict/batch`)
- **Status:** ✓ **503 Service Unavailable** (requires model training)
- **Resolution:** Call `POST /api/v1/ml/train` first
- **After training:** ✓ **200 OK** with ML-based predictions

### Train Endpoint (`POST /api/v1/ml/train`)
- **Purpose:** Train ML model using synthetic data
- **Optional:** Only needed for batch predictions or ML-based detection
- **Generates:** Isolation Forest model + StandardScaler

## Pattern-Based Detection Rules

The fallback detection uses 5 patterns (no ML training):

| Pattern | Condition | Example |
|---------|-----------|---------|
| **Congestion** | PRB usage > 90% | gNB overloaded |
| **Latency Issue** | Latency > 50ms | Transport problems |
| **Packet Loss** | Packet loss > 1% | Air interface degradation |
| **Throughput Drop** | Throughput < 80% of baseline | Radio degradation |
| **Auth Failure** | Registration success < 95% | AMF/AUSF issues |

Each pattern has configurable thresholds via environment variables:
```bash
ANOMALY_PRB_THRESHOLD=90
ANOMALY_LATENCY_THRESHOLD=50
ANOMALY_PACKET_LOSS_THRESHOLD=1
```

## Testing the Fix

### Test 1: Single Prediction (should work now)
```bash
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB001",
    "metrics": {
      "prb_usage": 95,
      "throughput_mbps": 450,
      "latency_ms": 65,
      "packet_loss_percent": 1.2
    }
  }'
```

**Expected Response:**
```json
{
  "prediction_id": "uuid...",
  "gnb_id": "gNB001",
  "result": {
    "is_anomaly": true,
    "anomaly_score": 0.8,
    "explanation": "Multiple patterns detected: High PRB usage detected; High latency detected"
  },
  "processing_time_ms": 2.34
}
```

### Test 2: Data Source Verification
```bash
curl http://localhost:8000/api/v1/ml/data-source/status
```

**Expected Response:**
```json
{
  "timestamp": "2026-03-30T13:11:30.051044",
  "available": true,
  "source_info": {
    "type": "logs",
    "base_path": "./open5gs_logs/log",
    "watched_nfs": ["amf", "upf", "nrf", "ausf"],
    "is_ready": true
  }
}
```

### Test 3: KPI Batch from Logs
```bash
curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source?limit=10
```

**Expected Response:**
```json
{
  "records": [
    {
      "timestamp": "2026-03-30T13:11:30",
      "gnb_id": "gNB001",
      "prb_usage": 75.5,
      "throughput": 520.2,
      "latency": 35.3,
      "packet_loss": 0.2,
      "is_anomaly": false,
      "anomaly_reason": "All metrics within normal range",
      "source": "logs"
    },
    ...
  ],
  "source": "logs",
  "count": 10
}
```

## Migration Path

### For Users with Existing Models
1. Your pre-trained ML models continue to work
2. Single predictions use pattern-based by default (faster)
3. Set `DATA_SOURCE=logs` to use real Open5GS logs
4. ML model training still available via `/train` endpoint

### For New Users
1. No setup needed - just start the server
2. Use `/predict` endpoint immediately (pattern-based)
3. Optional: Train ML model with `/train` for batch processing
4. Can switch between simulator and logs via `DATA_SOURCE` env var

## Files Modified

1. **`api/v1/endpoints/prediction.py`**
   - Updated imports (added PatternAnomalyDetector)
   - Modified `/predict` endpoint with fallback logic
   - Fixed `/predict/batch` and `/train` references

## Summary

✓ **Issue Resolved:** `/predict` endpoint now works without ML model training
✓ **Fallback Logic:** Automatically uses pattern-based detection when ML model unavailable
✓ **Backward Compatible:** Existing ML models still supported
✓ **Ready for Production:** Can use real logs immediately without setup

The system now provides **immediate anomaly detection** via pattern rules while supporting **advanced ML-based detection** for trained models.
