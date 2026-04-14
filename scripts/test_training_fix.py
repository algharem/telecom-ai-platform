#!/usr/bin/env python3
"""
Test script to validate the training column name fix.
This reproduces the exact error and confirms it's fixed.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.kpi_simulator import TelecomKPISimulator
from services.ml_detector import AnomalyDetector

def test_training_with_simulator_data():
    """Test that simulator data trains the ML detector without errors"""
    print("\n" + "="*60)
    print("TEST: Training ML Detector with Simulator Data")
    print("="*60)
    
    # Step 1: Generate training data
    print("\n1. Generating training data from simulator...")
    simulator = TelecomKPISimulator(base_stations=5)
    df = simulator.generate_training_data(hours=24, anomaly_rate=0.05)
    
    print(f"   Generated {len(df)} records")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Sample columns that caused error:")
    for col in ['throughput_mbps', 'latency_ms', 'packet_loss_percent']:
        if col in df.columns:
            print(f"     - {col}: {df[col].iloc[0]}")
    
    # Step 2: Initialize detector
    print("\n2. Initializing ML Detector...")
    detector = AnomalyDetector()
    print(f"   Expected feature columns: {detector.FEATURE_COLUMNS}")
    
    # Step 3: Train detector (this should have failed before the fix)
    print("\n3. Training detector (this used to fail with column name error)...")
    try:
        metrics = detector.train(df)
        print("   ✓ Training successful!")
        print(f"   Training metrics:")
        for key, value in metrics.items():
            print(f"     - {key}: {value}")
        
        # Step 4: Verify model is trained
        print("\n4. Verifying model...")
        assert detector.is_trained, "Model should be trained"
        print("   ✓ Model is trained and ready")
        
        # Step 5: Test prediction with KPIMetrics object
        print("\n5. Testing prediction with KPIMetrics...")
        from models.schemas import KPIMetrics, PredictionRequest
        
        metrics_obj = KPIMetrics(
            prb_usage=45.5,
            throughput_mbps=250.0,
            latency_ms=25.0,
            packet_loss_percent=0.1,
            registration_success_rate=99.5
        )
        
        pred_request = PredictionRequest(
            gnb_id="gNB_001",
            metrics=metrics_obj
        )
        
        result = detector.predict(pred_request)
        print(f"   ✓ Prediction successful")
        print(f"     - Is anomaly: {result.is_anomaly}")
        print(f"     - Anomaly score: {result.anomaly_score:.3f}")
        print(f"     - Confidence: {result.confidence:.3f}")
        
        print("\n" + "="*60)
        print("TEST PASSED: Training fix is working correctly!")
        print("="*60)
        return True
        
    except KeyError as e:
        print(f"   ✗ KeyError (the original bug): {e}")
        print(f"     This means the fix didn't work properly.")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_training_with_simulator_data()
    sys.exit(0 if success else 1)
