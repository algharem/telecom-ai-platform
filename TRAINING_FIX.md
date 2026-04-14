# Training Error Fix: Column Name Mismatch

## The Problem

When you tried to train the ML model via `/api/v1/ml/train`, you got this error:

```
500 Internal Server Error
Training failed: "['throughput', 'latency', 'packet_loss'] not in index"
```

## Root Cause

There was a **column naming mismatch** between two components:

### Simulator (Generator)
Generated columns with suffixes:
- `throughput_mbps` (line 137 in kpi_simulator.py)
- `latency_ms` (line 138)
- `packet_loss_percent` (line 139)

### ML Detector (Consumer)
Expected columns without suffixes:
- `throughput` (line 32 in ml_detector.py)
- `latency` (line 32)
- `packet_loss` (line 32)

When the detector tried to access `df[['prb_usage', 'throughput', 'latency', 'packet_loss']]`, the DataFrame only had `throughput_mbps`, `latency_ms`, and `packet_loss_percent`, causing a KeyError.

## The Fix

Updated the `train()` method in `services/ml_detector.py` to normalize column names before processing:

```python
# Normalize column names (handle both naming conventions)
df_normalized = df.copy()
column_mapping = {
    'throughput_mbps': 'throughput',
    'latency_ms': 'latency',
    'packet_loss_percent': 'packet_loss'
}
df_normalized = df_normalized.rename(columns=column_mapping)

# Now prepare features with normalized columns
X = df_normalized[self.FEATURE_COLUMNS].copy()
```

This approach:
- **Handles both naming conventions** (old and new)
- **Works with the simulator** (both old and new column names)
- **Works with real logs** (flexible naming)
- **No breaking changes** to existing code

## Testing

Run the validation script to confirm the fix:

```bash
python scripts/test_training_fix.py
```

Expected output:
```
✓ Training successful!
✓ Model is trained and ready
✓ Prediction successful
TEST PASSED: Training fix is working correctly!
```

## Now Training Works

Try the endpoint again:

```bash
curl -X POST http://localhost:8000/api/v1/ml/train \
  -H "Content-Type: application/json" \
  -d {
    "duration_hours": 24,
    "anomaly_rate": 0.05
  }
```

Expected response:
```json
{
  "status": "success",
  "training_metrics": {
    "training_samples": 240,
    "detected_anomalies": 12,
    "anomaly_ratio": 0.05,
    ...
  },
  "model_info": {
    "is_trained": true,
    "feature_columns": ["prb_usage", "throughput", "latency", "packet_loss"]
  }
}
```

## Impact

After training, the ML-based detection becomes available:
- `/api/v1/ml/predict` - Uses ML model if trained, falls back to patterns
- `/api/v1/ml/predict/batch` - Batch prediction with trained model

## Related Files

- `services/ml_detector.py` - Fixed train() method
- `scripts/test_training_fix.py` - Validation script
- `services/kpi_simulator.py` - Data generator (unchanged)
- `api/v1/endpoints/prediction.py` - Prediction endpoints (uses detector)

## Timeline

1. Simulator generates training data with suffixed column names
2. ML detector now normalizes column names before training
3. Model trains successfully and is saved to `data/anomaly_detector.pkl`
4. Predictions use the trained model (or fall back to pattern detection)
