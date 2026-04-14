"""
Unit tests for AnomalyDetector service.
Tests pattern-based anomaly detection logic.
"""

import pytest
from datetime import datetime, timedelta
from services.anomaly_detector import AnomalyDetector, AnomalyThresholds
from services.data_provider import KPIRecord


class TestAnomalyThresholds:
    """Test threshold configuration"""
    
    def test_default_thresholds(self):
        """Test default threshold values"""
        thresholds = AnomalyThresholds()
        
        assert thresholds.prb_usage_percent == 90.0
        assert thresholds.latency_ms == 50.0
        assert thresholds.packet_loss_percent == 1.0
        assert thresholds.registration_success_rate_percent == 95.0
        assert thresholds.throughput_drop_percent == 20.0
        assert thresholds.min_consecutive_for_confirmation == 2
    
    def test_custom_thresholds(self):
        """Test custom threshold initialization"""
        thresholds = AnomalyThresholds(
            prb_usage_percent=85.0,
            latency_ms=40.0,
            packet_loss_percent=0.5
        )
        
        assert thresholds.prb_usage_percent == 85.0
        assert thresholds.latency_ms == 40.0
        assert thresholds.packet_loss_percent == 0.5


class TestAnomalyDetector:
    """Test anomaly detection logic"""
    
    @pytest.fixture
    def detector(self):
        """Create detector with default thresholds"""
        return AnomalyDetector()
    
    @pytest.fixture
    def sample_record(self):
        """Create a sample KPI record"""
        return KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=50.0,
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
    
    def test_normal_kpi_no_anomaly(self, detector, sample_record):
        """Test that normal KPIs don't trigger anomalies"""
        is_anomaly, reason = detector.detect(sample_record)
        
        assert is_anomaly is False
        assert reason is None
    
    def test_high_prb_usage_anomaly(self, detector):
        """Test high PRB usage detection"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=95.0,  # Above 90% threshold
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        
        assert is_anomaly is True
        assert "PRB" in reason or "prb" in reason.lower()
        assert "95.0" in reason
    
    def test_high_latency_anomaly(self, detector):
        """Test high latency detection"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=50.0,
            throughput=100.0,
            latency=60.0,  # Above 50ms threshold
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        
        assert is_anomaly is True
        assert "latency" in reason.lower()
        assert "60.0" in reason
    
    def test_high_packet_loss_anomaly(self, detector):
        """Test high packet loss detection"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=50.0,
            throughput=100.0,
            latency=20.0,
            packet_loss=2.5,  # Above 1% threshold
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        
        assert is_anomaly is True
        assert "packet loss" in reason.lower()
        assert "2.5" in reason
    
    def test_multiple_anomalies(self, detector):
        """Test detection of multiple simultaneous anomalies"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=95.0,  # High PRB
            throughput=100.0,
            latency=60.0,    # High latency
            packet_loss=2.5, # High packet loss
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        
        assert is_anomaly is True
        # Should contain all three anomaly reasons
        assert "PRB" in reason or "prb" in reason.lower()
        assert "latency" in reason.lower()
        assert "packet loss" in reason.lower()
    
    def test_throughput_drop_detection(self, detector):
        """Test throughput drop detection against history"""
        gnb_id = "gNB-001"
        base_time = datetime.now()
        
        # Add baseline records with high throughput
        for i in range(5):
            record = KPIRecord(
                timestamp=base_time - timedelta(minutes=i),
                gnb_id=gnb_id,
                prb_usage=50.0,
                throughput=200.0,  # Baseline throughput
                latency=20.0,
                packet_loss=0.1,
                is_anomaly=False,
                source="simulator"
            )
            detector.detect(record)
        
        # Now add record with significant throughput drop (>20%)
        drop_record = KPIRecord(
            timestamp=base_time + timedelta(minutes=1),
            gnb_id=gnb_id,
            prb_usage=50.0,
            throughput=140.0,  # 30% drop from 200
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(drop_record)
        
        assert is_anomaly is True
        assert "throughput" in reason.lower() or "drop" in reason.lower()
    
    def test_batch_detection(self, detector):
        """Test batch anomaly detection"""
        records = [
            KPIRecord(
                timestamp=datetime.now(),
                gnb_id="gNB-001",
                prb_usage=50.0,
                throughput=100.0,
                latency=20.0,
                packet_loss=0.1,
                source="simulator"
            ),
            KPIRecord(
                timestamp=datetime.now(),
                gnb_id="gNB-002",
                prb_usage=95.0,  # Anomaly
                throughput=100.0,
                latency=20.0,
                packet_loss=0.1,
                source="simulator"
            ),
            KPIRecord(
                timestamp=datetime.now(),
                gnb_id="gNB-003",
                prb_usage=50.0,
                throughput=100.0,
                latency=20.0,
                packet_loss=0.1,
                source="simulator"
            )
        ]
        
        results = detector.detect_batch(records)
        
        assert len(results) == 3
        assert results[0][1] is False  # First record normal
        assert results[1][1] is True   # Second record anomaly
        assert results[2][1] is False  # Third record normal
    
    def test_detector_statistics(self, detector):
        """Test detector statistics tracking"""
        # Process some records
        normal_record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=50.0,
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        anomaly_record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=95.0,
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        detector.detect(normal_record)
        detector.detect(normal_record)
        detector.detect(anomaly_record)
        
        stats = detector.get_stats()
        
        assert stats["total_checked"] == 3
        assert stats["total_anomalies"] == 1
        assert stats["anomaly_rate"] == pytest.approx(33.33, rel=0.1)
        assert "tracked_gnbs" in stats
    
    def test_custom_thresholds(self):
        """Test detector with custom thresholds"""
        custom_thresholds = {
            "prb_usage_percent": 80.0,
            "latency_ms": 30.0,
            "packet_loss_percent": 0.5
        }
        
        detector = AnomalyDetector(thresholds=custom_thresholds)
        
        # Record that would be normal with defaults but anomalous with custom
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=85.0,  # Above 80% custom threshold
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        
        assert is_anomaly is True
        assert "PRB" in reason or "prb" in reason.lower()
    
    def test_update_thresholds_runtime(self, detector):
        """Test updating thresholds at runtime"""
        # Initially normal
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=85.0,
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, _ = detector.detect(record)
        assert is_anomaly is False  # Below 90% default
        
        # Update threshold to be more strict
        detector.update_thresholds({"prb_usage_percent": 80.0})
        
        is_anomaly, reason = detector.detect(record)
        assert is_anomaly is True  # Now above 80%
    
    def test_history_tracking_per_gnb(self, detector):
        """Test that history is tracked separately per gNB"""
        base_time = datetime.now()
        
        # Add records for two different gNBs
        for i in range(3):
            record1 = KPIRecord(
                timestamp=base_time - timedelta(minutes=i),
                gnb_id="gNB-001",
                prb_usage=50.0,
                throughput=200.0,
                latency=20.0,
                packet_loss=0.1,
                source="simulator"
            )
            detector.detect(record1)
            
            record2 = KPIRecord(
                timestamp=base_time - timedelta(minutes=i),
                gnb_id="gNB-002",
                prb_usage=50.0,
                throughput=100.0,  # Different baseline
                latency=20.0,
                packet_loss=0.1,
                source="simulator"
            )
            detector.detect(record2)
        
        stats = detector.get_stats()
        assert stats["tracked_gnbs"] == 2
    
    def test_anomaly_classification(self, detector):
        """Test anomaly type classification"""
        # Congestion (high PRB)
        congestion_record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=95.0,
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        detector.detect(congestion_record)
        
        stats = detector.get_stats()
        assert "congestion" in stats["anomaly_breakdown"]


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    @pytest.fixture
    def detector(self):
        return AnomalyDetector()
    
    def test_boundary_prb_usage(self, detector):
        """Test PRB at exactly threshold boundary"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=90.0,  # Exactly at threshold
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, _ = detector.detect(record)
        # At threshold should not be anomaly (needs to be > threshold)
        assert is_anomaly is False
    
    def test_just_above_boundary_prb(self, detector):
        """Test PRB just above threshold"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=90.01,  # Just above threshold
            throughput=100.0,
            latency=20.0,
            packet_loss=0.1,
            source="simulator"
        )
        
        is_anomaly, _ = detector.detect(record)
        assert is_anomaly is True
    
    def test_zero_values(self, detector):
        """Test with zero metric values"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=0.0,
            throughput=0.0,
            latency=0.0,
            packet_loss=0.0,
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        assert is_anomaly is False
    
    def test_extreme_values(self, detector):
        """Test with extreme metric values"""
        record = KPIRecord(
            timestamp=datetime.now(),
            gnb_id="gNB-001",
            prb_usage=100.0,
            throughput=10000.0,
            latency=500.0,
            packet_loss=50.0,
            source="simulator"
        )
        
        is_anomaly, reason = detector.detect(record)
        assert is_anomaly is True
        # Should detect multiple anomalies
        assert "PRB" in reason or "prb" in reason.lower()
