#!/usr/bin/env python3
"""
Validation script for Open5GS Log Parser Integration.

Tests all phases to ensure proper integration:
- Phase 1: Data provider abstraction
- Phase 2: Log aggregation
- Phase 3: Anomaly detection
- Phase 4: API integration
- Phase 5: Monitoring

Run with: python scripts/validate_integration.py
"""

import sys
from datetime import datetime, timedelta

def test_phase_1_data_provider():
    """Test Phase 1: Data Source Abstraction Layer"""
    print("\n" + "="*60)
    print("PHASE 1: Data Source Abstraction Layer")
    print("="*60)
    
    try:
        from services.data_provider import (
            create_data_provider, 
            get_provider_config,
            KPIRecord
        )
        
        # Test simulator provider
        print("\n[TEST 1.1] Creating simulator data provider...")
        config = get_provider_config("simulator")
        provider = create_data_provider("simulator", config)
        assert provider is not None, "Provider creation failed"
        print("✓ Simulator provider created successfully")
        
        # Test provider interface
        print("\n[TEST 1.2] Testing provider interface...")
        assert provider.is_available(), "Provider not available"
        assert provider.get_source_info() is not None, "No source info"
        print("✓ Provider interface working")
        
        # Test getting batch
        print("\n[TEST 1.3] Fetching KPI batch...")
        batch = provider.get_next_batch(limit=10)
        assert len(batch) > 0, "No records fetched"
        assert all(isinstance(r, KPIRecord) for r in batch), "Wrong record type"
        print(f"✓ Got {len(batch)} KPI records from provider")
        
        # Verify KPIRecord structure
        print("\n[TEST 1.4] Verifying KPIRecord structure...")
        record = batch[0]
        assert hasattr(record, 'timestamp'), "Missing timestamp"
        assert hasattr(record, 'gnb_id'), "Missing gnb_id"
        assert hasattr(record, 'prb_usage'), "Missing prb_usage"
        assert hasattr(record, 'throughput'), "Missing throughput"
        assert hasattr(record, 'latency'), "Missing latency"
        assert hasattr(record, 'packet_loss'), "Missing packet_loss"
        print(f"✓ KPIRecord structure valid: {record.gnb_id} @ {record.timestamp}")
        
        provider.close()
        return True, "PHASE 1 PASSED"
        
    except Exception as e:
        return False, f"PHASE 1 FAILED: {str(e)}"


def test_phase_2_aggregation():
    """Test Phase 2: Log Parsing & Aggregation Engine"""
    print("\n" + "="*60)
    print("PHASE 2: Log Parsing & Aggregation Engine")
    print("="*60)
    
    try:
        from parsers.aggregators.gnb_aggregator import GnBMetricsAggregator
        from parsers.mappers.nf_to_gnb_mapper import MapperFactory
        
        # Test aggregator creation
        print("\n[TEST 2.1] Creating gNB metrics aggregator...")
        aggregator = GnBMetricsAggregator(window_seconds=60)
        assert aggregator is not None, "Aggregator creation failed"
        print("✓ gNB aggregator created")
        
        # Test mappers
        print("\n[TEST 2.2] Testing NF mappers...")
        nf_types = ['amf', 'upf', 'nrf', 'ausf']
        mappers = {}
        for nf in nf_types:
            mapper = MapperFactory.get_mapper(nf)
            assert mapper is not None, f"Failed to get mapper for {nf}"
            mappers[nf] = mapper
        print(f"✓ All {len(nf_types)} NF mappers loaded: {', '.join(nf_types)}")
        
        # Test adding metrics
        print("\n[TEST 2.3] Adding metrics to aggregator...")
        for i in range(20):
            aggregator.add_nf_metric(
                gnb_id="gNB_001",
                nf_type="amf",
                metric_name="registration_latency",
                value=40 + i,
                timestamp=datetime.now()
            )
        
        stats = aggregator.get_stats()
        assert stats['total_metrics_added'] == 20, "Metrics not tracked"
        print(f"✓ Added 20 metrics, aggregator tracking working")
        
        # Test mapper extraction
        print("\n[TEST 2.4] Testing metric mapping...")
        sample_data = {
            'message': 'Added: Number of AMF-UEs is now 5',
            'count': 5
        }
        mapper = mappers['amf']
        gnb_id = mapper.extract_gnb_id(sample_data)
        metrics = mapper.map_metrics("gNB_001", sample_data, datetime.now())
        assert isinstance(metrics, list), "Mapper should return list"
        print(f"✓ Metrics mapping working: extracted {len(metrics) if metrics else 0} metrics")
        
        aggregator.close() if hasattr(aggregator, 'close') else None
        return True, "PHASE 2 PASSED"
        
    except Exception as e:
        return False, f"PHASE 2 FAILED: {str(e)}"


def test_phase_3_anomaly_detection():
    """Test Phase 3: Anomaly Detection with Thresholds"""
    print("\n" + "="*60)
    print("PHASE 3: Anomaly Detection with Thresholds")
    print("="*60)
    
    try:
        from services.anomaly_detector import AnomalyDetector
        from services.data_provider import KPIRecord
        
        # Test detector creation
        print("\n[TEST 3.1] Creating anomaly detector...")
        detector = AnomalyDetector()
        assert detector is not None, "Detector creation failed"
        print("✓ Anomaly detector created with default thresholds")
        
        # Test normal record
        print("\n[TEST 3.2] Testing normal KPI (no anomaly)...")
        normal_record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB_001",
            prb_usage=50.0,
            throughput=500.0,
            latency=25.0,
            packet_loss=0.1,
            source="test"
        )
        is_anomaly, reason = detector.detect(normal_record)
        assert not is_anomaly, "Normal record flagged as anomaly"
        print("✓ Normal record correctly identified")
        
        # Test anomalous record - high PRB
        print("\n[TEST 3.3] Testing anomalous KPI (high PRB)...")
        anomaly_record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB_001",
            prb_usage=95.0,  # > 90 threshold
            throughput=500.0,
            latency=25.0,
            packet_loss=0.1,
            source="test"
        )
        is_anomaly, reason = detector.detect(anomaly_record)
        assert is_anomaly, "Anomalous record not detected"
        assert "PRB" in reason, "Reason should mention PRB"
        print(f"✓ Anomaly detected: {reason}")
        
        # Test batch detection
        print("\n[TEST 3.4] Testing batch anomaly detection...")
        batch = [normal_record] * 5 + [anomaly_record] * 3
        results = detector.detect_batch(batch)
        assert len(results) == 8, "Batch size mismatch"
        anomaly_count = sum(1 for _, is_anom, _ in results if is_anom)
        assert anomaly_count == 3, f"Expected 3 anomalies, got {anomaly_count}"
        print(f"✓ Batch detection working: {anomaly_count}/8 anomalies detected")
        
        # Test detector stats
        print("\n[TEST 3.5] Testing detector statistics...")
        stats = detector.get_stats()
        assert stats['total_checked'] == 8, "Stats not tracking"
        assert stats['total_anomalies'] == 3, "Anomaly count wrong"
        print(f"✓ Detector stats: {stats['total_checked']} checked, {stats['total_anomalies']} anomalies")
        
        return True, "PHASE 3 PASSED"
        
    except Exception as e:
        return False, f"PHASE 3 FAILED: {str(e)}"


def test_phase_4_api_integration():
    """Test Phase 4: API Integration"""
    print("\n" + "="*60)
    print("PHASE 4: Data Flow Integration into API")
    print("="*60)
    
    try:
        from api.v1.endpoints import prediction, monitoring
        
        # Test prediction endpoint exists
        print("\n[TEST 4.1] Checking prediction endpoints...")
        assert hasattr(prediction, 'router'), "Prediction router not found"
        routes = [r.path for r in prediction.router.routes]
        assert any('kpi' in r for r in routes), "KPI endpoint not found"
        print(f"✓ Prediction endpoints registered: {len(routes)} routes")
        
        # Test monitoring endpoint exists
        print("\n[TEST 4.2] Checking monitoring endpoints...")
        assert hasattr(monitoring, 'router'), "Monitoring router not found"
        routes = [r.path for r in monitoring.router.routes]
        assert len(routes) >= 8, f"Expected 8+ monitoring routes, got {len(routes)}"
        print(f"✓ Monitoring endpoints registered: {len(routes)} routes")
        
        # Test API router integration
        print("\n[TEST 4.3] Checking API router...")
        from api.v1.api import api_router
        assert api_router is not None, "API router not found"
        print("✓ API router properly configured")
        
        return True, "PHASE 4 PASSED"
        
    except Exception as e:
        return False, f"PHASE 4 FAILED: {str(e)}"


def test_phase_5_monitoring():
    """Test Phase 5: Monitoring & Observability"""
    print("\n" + "="*60)
    print("PHASE 5: Monitoring & Observability")
    print("="*60)
    
    try:
        from services.pipeline_monitor import PipelineMonitor
        
        # Test monitor creation
        print("\n[TEST 5.1] Creating pipeline monitor...")
        monitor = PipelineMonitor(retention_minutes=60)
        assert monitor is not None, "Monitor creation failed"
        print("✓ Pipeline monitor created")
        
        # Test recording parse metrics
        print("\n[TEST 5.2] Recording parse metrics...")
        monitor.record_parse(
            nf_type="amf",
            total_events=100,
            successful_parses=98,
            data_freshness_seconds=2.5
        )
        print("✓ Parse metrics recorded")
        
        # Test recording anomalies
        print("\n[TEST 5.3] Recording anomalies...")
        monitor.record_anomaly("gNB_001", is_anomaly=True, anomaly_type="congestion")
        monitor.record_anomaly("gNB_001", is_anomaly=False)
        monitor.record_anomaly("gNB_002", is_anomaly=True, anomaly_type="latency")
        print("✓ Anomaly records created")
        
        # Test health status
        print("\n[TEST 5.4] Getting health status...")
        health = monitor.get_health_status()
        assert 'status' in health, "No status in health"
        assert 'uptime_seconds' in health, "No uptime in health"
        assert 'total_records_processed' in health, "No record count in health"
        print(f"✓ Health status: {health['status']}, uptime: {health['uptime_seconds']:.1f}s")
        
        # Test NF stats
        print("\n[TEST 5.5] Getting per-NF stats...")
        nf_stats = monitor.get_nf_stats("amf")
        assert nf_stats['nf_type'] == 'amf', "Wrong NF type"
        assert nf_stats['total_parsed'] == 98, "Parse count wrong"
        print(f"✓ NF stats: {nf_stats['total_parsed']} parsed, {nf_stats['total_errors']} errors")
        
        # Test gNB stats
        print("\n[TEST 5.6] Getting per-gNB stats...")
        gnb_stats = monitor.get_gnb_stats("gNB_001")
        assert gnb_stats['gnb_id'] == 'gNB_001', "Wrong gNB"
        assert gnb_stats['total_anomalies'] == 1, "Anomaly count wrong"
        print(f"✓ gNB stats: {gnb_stats['total_records']} records, {gnb_stats['total_anomalies']} anomalies")
        
        # Test comprehensive stats
        print("\n[TEST 5.7] Getting comprehensive stats...")
        all_stats = monitor.get_stats()
        assert 'health' in all_stats, "No health in stats"
        assert 'nf_breakdown' in all_stats, "No NF breakdown"
        assert 'gnb_breakdown' in all_stats, "No gNB breakdown"
        print(f"✓ Comprehensive stats: {len(all_stats)} sections")
        
        return True, "PHASE 5 PASSED"
        
    except Exception as e:
        return False, f"PHASE 5 FAILED: {str(e)}"


def test_backward_compatibility():
    """Test backward compatibility with existing code"""
    print("\n" + "="*60)
    print("BACKWARD COMPATIBILITY CHECK")
    print("="*60)
    
    try:
        # Test existing simulator still works
        print("\n[TEST BC.1] Testing existing KPI simulator...")
        from services.kpi_simulator import TelecomKPISimulator
        sim = TelecomKPISimulator(base_stations=5)
        df = sim.generate_training_data(hours=1, anomaly_rate=0.05)
        assert len(df) > 0, "Simulator not generating data"
        print(f"✓ Simulator still works: {len(df)} records generated")
        
        # Test existing ML detector still works
        print("\n[TEST BC.2] Testing existing ML detector...")
        from services.ml_detector import AnomalyDetector as MLDetector
        ml_det = MLDetector()
        assert ml_det is not None, "ML detector not available"
        print("✓ Existing ML detector still available")
        
        return True, "BACKWARD COMPATIBILITY PASSED"
        
    except Exception as e:
        return False, f"BACKWARD COMPATIBILITY FAILED: {str(e)}"


def main():
    """Run all validation tests"""
    print("\n" + "█"*60)
    print("Open5GS Log Parser Integration Validation Suite")
    print("█"*60)
    
    tests = [
        ("Phase 1: Data Provider Abstraction", test_phase_1_data_provider),
        ("Phase 2: Log Aggregation", test_phase_2_aggregation),
        ("Phase 3: Anomaly Detection", test_phase_3_anomaly_detection),
        ("Phase 4: API Integration", test_phase_4_api_integration),
        ("Phase 5: Monitoring", test_phase_5_monitoring),
        ("Backward Compatibility", test_backward_compatibility),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed, message = test_func()
            results.append((test_name, passed, message))
        except Exception as e:
            results.append((test_name, False, f"Exception: {str(e)}"))
    
    # Print summary
    print("\n" + "█"*60)
    print("VALIDATION SUMMARY")
    print("█"*60)
    
    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    
    for name, passed, message in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {name}")
        print(f"  → {message}")
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed_count}/{total_count} tests passed")
    print("="*60)
    
    if passed_count == total_count:
        print("\n✓ ALL TESTS PASSED - Implementation is valid!")
        return 0
    else:
        print(f"\n✗ {total_count - passed_count} tests failed - Please review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
