# Training Error Resolved

## Error Details

**Endpoint:** `POST /api/v1/ml/train`

**Status Code:** 500 Internal Server Error

**Error Message:**
```
Training failed: "['throughput', 'latency', 'packet_loss'] not in index"
```

**Log Output:**
```
2026-03-30T13:20:35.769626 | ERROR | prediction.py:142
Training failed: "['throughput', 'latency', 'packet_loss'] not in index"
```

---

## What Happened

1. **Simulator** generates training data with these columns:
   - `throughput_mbps`
   - `latency_ms`
   - `packet_loss_percent`

2. **ML Detector** tried to access columns with different names:
   - `throughput`
   - `latency`
   - `packet_loss`

3. **Result:** Pandas KeyError → 500 error

---

## Solution Applied

Updated `services/ml_detector.py` line 78-101:

**Before:**
```python
def train(self, df: pd.DataFrame) -> Dict:
    logger.info(f"Training model on {len(df)} records")
    X = df[self.FEATURE_COLUMNS].copy()  # ← FAILS: columns don't exist
```

**After:**
```python
def train(self, df: pd.DataFrame) -> Dict:
    logger.info(f"Training model on {len(df)} records")
    
    # Normalize column names
    df_normalized = df.copy()
    column_mapping = {
        'throughput_mbps': 'throughput',
        'latency_ms': 'latency',
        'packet_loss_percent': 'packet_loss'
    }
    df_normalized = df_normalized.rename(columns=column_mapping)
    
    X = df_normalized[self.FEATURE_COLUMNS].copy()  # ← NOW WORKS
```

---

## Verification

Run the test to confirm:

```bash
python /vercel/share/v0-project/scripts/test_training_fix.py
```

Expected result:
```
✓ Training successful!
✓ Model is trained and ready
✓ Prediction successful
TEST PASSED: Training fix is working correctly!
```

---

## Next Steps

1. **Train the model:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/ml/train
   ```

2. **Use trained model for predictions:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/ml/predict \
     -H "Content-Type: application/json" \
     -d '{"gnb_id": "gNB_001", "metrics": {...}}'
   ```

3. **Or use pattern-based detection immediately** (no training needed):
   ```bash
   curl -X POST http://localhost:8000/api/v1/ml/kpi/batch/from-data-source
   ```

---

## File Changes

- **Modified:** `services/ml_detector.py` (train method)
- **Added:** `scripts/test_training_fix.py` (validation)
- **Added:** `TRAINING_FIX.md` (detailed documentation)
- **Added:** `TRAINING_ERROR_RESOLVED.md` (this file)

All changes are backward compatible and don't break existing functionality.
