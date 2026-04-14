#!/usr/bin/env python3
"""
Simple script to fetch current Open5GS KPI data from Prometheus
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.data_provider import PrometheusDataProvider
from datetime import datetime

# Initialize provider with config
config = {
    "prometheus_url": "http://172.25.0.36:9090",
    "gnb_id": "gNB-001"
}

print("=" * 80)
print("Fetching Open5GS KPI Data from Prometheus")
print("=" * 80)
print(f"Prometheus URL: {config['prometheus_url']}")
print(f"gNB ID: {config['gnb_id']}")
print(f"Timestamp: {datetime.now().isoformat()}")
print("=" * 80)

provider = PrometheusDataProvider(config)

# Check availability
if not provider.is_available():
    print("\n❌ ERROR: Cannot connect to Prometheus!")
    print(f"   Please ensure Prometheus is running at {config['prometheus_url']}")
    print("\nTroubleshooting:")
    print("  1. Check if Prometheus container is running: docker ps | grep prometheus")
    print("  2. Verify network connectivity: curl http://172.25.0.36:9090/-/healthy")
    print("  3. Check Prometheus logs: docker logs <prometheus_container_id>")
    sys.exit(1)

print("\n✅ Prometheus connection successful!")

# Fetch current KPI
records = provider.get_next_batch(limit=1)

if records:
    record = records[0]
    print("\n" + "-" * 80)
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
    
    print("=" * 80)
else:
    print("\n❌ No KPI data returned from Prometheus")
    sys.exit(1)

provider.close()
