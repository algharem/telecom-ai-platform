#!/usr/bin/env python3
"""
Fetch simulated Open5GS-like KPI data
Useful when Prometheus is not accessible
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.kpi_simulator import TelecomKPISimulator
from services.data_provider import KPIRecord
from datetime import datetime

print("=" * 80)
print("Open5GS KPI Data (Simulated)")
print("=" * 80)
print(f"Timestamp: {datetime.now().isoformat()}")
print(f"Mode: Simulator (Prometheus not available)")
print("=" * 80)

# Initialize simulator with realistic Open5GS-like parameters
simulator = TelecomKPISimulator(
    base_stations=10,
    random_seed=None  # Use system time for variety
)

print("\n📡 Simulating gNB-001 metrics...\n")

# Generate a single KPI record
kpi_metrics = simulator.generate_single_kpi(gnb_id="gNB-001", scenario="normal")

# Create KPIRecord from metrics
from datetime import datetime
record = KPIRecord(
    timestamp=datetime.now(),
    gnb_id="gNB-001",
    prb_usage=kpi_metrics.prb_usage,
    throughput=kpi_metrics.throughput,
    latency=kpi_metrics.latency,
    packet_loss=kpi_metrics.packet_loss,
    source="simulator"
)

print("-" * 80)
print("Current KPI Metrics:")
print("-" * 80)
print(f"  Timestamp:    {record.timestamp}")
print(f"  gNB ID:       {record.gnb_id}")
print(f"  PRB Usage:    {record.prb_usage:.1f}%")
print(f"  Throughput:   {record.throughput:.1f} Mbps")
print(f"  Latency:      {record.latency:.1f} ms")
print(f"  Packet Loss:  {record.packet_loss:.2f}%")
print(f"  Source:       {record.source}")
print("-" * 80)

# Anomaly check
from services.anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
is_anomaly, reason = detector.detect(record)

if is_anomaly:
    print(f"\n⚠️  ANOMALY DETECTED: {reason}")
else:
    print("\n✅ Status: NORMAL - All metrics within thresholds")

print("\n" + "=" * 80)
print("Note: This is simulated data. For live Open5GS data, ensure:")
print("  • Prometheus is running and accessible")
print("  • Open5GS metrics are being exported to Prometheus")
print("  • Network connectivity to Prometheus endpoint")
print("=" * 80)
