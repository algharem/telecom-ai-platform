#!/usr/bin/env python3
"""
Test script to validate the prediction endpoint fix.
Tests both ML-based and pattern-based anomaly detection.
"""

import httpx
import asyncio
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1/ml"

async def test_prediction_endpoints():
    """Test prediction endpoints with and without model training"""
    
    async with httpx.AsyncClient(timeout=10) as client:
        print("\n" + "="*70)
        print("TESTING PREDICTION ENDPOINTS")
        print("="*70)
        
        # Test 1: Single prediction (should work with pattern-based detection)
        print("\n1. Testing single prediction with pattern-based detection...")
        prediction_payload = {
            "gnb_id": "gNB001",
            "metrics": {
                "prb_usage": 95.5,
                "throughput_mbps": 450.2,
                "latency_ms": 65.3,
                "packet_loss_percent": 1.2
            }
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/predict",
                json=prediction_payload
            )
            if response.status_code == 200:
                result = response.json()
                print(f"   ✓ Prediction successful")
                print(f"   - gNB: {result['gnb_id']}")
                print(f"   - Is Anomaly: {result['result']['is_anomaly']}")
                print(f"   - Anomaly Score: {result['result']['anomaly_score']}")
                print(f"   - Explanation: {result['result']['explanation']}")
                print(f"   - Processing Time: {result['processing_time_ms']:.2f}ms")
            else:
                print(f"   ✗ Failed with status {response.status_code}")
                print(f"   - Response: {response.text}")
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
        
        # Test 2: Batch endpoint without trained model
        print("\n2. Testing batch prediction without trained model...")
        batch_payload = [
            {
                "gnb_id": f"gNB00{i}",
                "metrics": {
                    "prb_usage": 50.0 + i*10,
                    "throughput_mbps": 300.0 + i*50,
                    "latency_ms": 30.0 + i*5,
                    "packet_loss_percent": 0.1 + i*0.1
                }
            }
            for i in range(3)
        ]
        
        try:
            response = await client.post(
                f"{BASE_URL}/predict/batch",
                json=batch_payload
            )
            if response.status_code == 503:
                print(f"   ✓ Correctly returns 503 (expected: model not trained)")
                result = response.json()
                print(f"   - Message: {result.get('detail', 'N/A')}")
            elif response.status_code == 200:
                print(f"   ✗ Unexpected success (model should not be trained)")
            else:
                print(f"   ? Unexpected status {response.status_code}")
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
        
        # Test 3: Check data source status
        print("\n3. Testing data source status endpoint...")
        try:
            response = await client.get(f"{BASE_URL}/data-source/status")
            if response.status_code == 200:
                result = response.json()
                print(f"   ✓ Status check successful")
                print(f"   - Data Source: {result.get('source_info', {}).get('type', 'unknown')}")
                print(f"   - Available: {result.get('available', False)}")
            else:
                print(f"   ✗ Failed with status {response.status_code}")
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
        
        # Test 4: Get KPI batch from data source
        print("\n4. Testing KPI batch from data source...")
        try:
            response = await client.post(
                f"{BASE_URL}/kpi/batch/from-data-source?limit=5"
            )
            if response.status_code == 200:
                result = response.json()
                print(f"   ✓ Batch fetch successful")
                print(f"   - Records returned: {result.get('count', 0)}")
                print(f"   - Source: {result.get('source', 'unknown')}")
                if result.get('records'):
                    first_record = result['records'][0]
                    print(f"   - First record gNB: {first_record.get('gnb_id')}")
                    print(f"   - First record is_anomaly: {first_record.get('is_anomaly')}")
            else:
                print(f"   ✗ Failed with status {response.status_code}")
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
        
        # Test 5: Monitoring endpoints
        print("\n5. Testing monitoring endpoints...")
        try:
            response = await client.get("/api/v1/monitoring/health")
            if response.status_code == 200:
                result = response.json()
                print(f"   ✓ Health check successful")
                print(f"   - Status: {result.get('status', 'unknown')}")
            else:
                print(f"   ✗ Failed with status {response.status_code}")
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print("\nKey Changes:")
        print("  ✓ /predict endpoint now uses pattern-based detection (no model training needed)")
        print("  ✓ Falls back to pattern-based if ML model not trained")
        print("  ✓ /predict/batch still requires trained ML model")
        print("  ✓ /train endpoint available to train the ML model if desired")
        print("\nExpected Behavior:")
        print("  ✓ Single predictions work immediately")
        print("  ✓ Batch predictions require model training")
        print("  ✓ Pattern-based detection uses threshold rules")
        print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_prediction_endpoints())
