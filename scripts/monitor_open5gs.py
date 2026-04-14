#!/usr/bin/env python3
"""
Real-time Open5GS KPI Monitor
Fetches and displays live metrics from Prometheus/Open5GS
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.data_provider import PrometheusDataProvider
from services.anomaly_detector import AnomalyDetector


def monitor_open5gs(interval_seconds=5, show_anomalies=True):
    """
    Continuously monitor Open5GS KPIs
    
    Args:
        interval_seconds: Fetch interval in seconds
        show_anomalies: Enable anomaly detection
    """
    print("=" * 80)
    print("Open5GS Real-Time KPI Monitor")
    print("=" * 80)
    print(f"Prometheus URL: http://172.25.0.36:9090")
    print(f"Target gNB: gNB-001")
    print(f"Update Interval: {interval_seconds}s")
    print(f"Anomaly Detection: {'Enabled' if show_anomalies else 'Disabled'}")
    print("=" * 80)
    print()
    
    # Initialize services
    config = {
        "prometheus_url": "http://172.25.0.36:9090",
        "gnb_id": "gNB-001"
    }
    provider = PrometheusDataProvider(config)
    
    detector = AnomalyDetector() if show_anomalies else None
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Fetch KPI from Open5GS
            records = provider.get_next_batch(limit=1)
            record = records[0] if records else None
            
            if record:
                # Display KPI
                print(f"\n[{timestamp}] Iteration #{iteration}")
                print("-" * 60)
                print(f"  PRB Usage:      {record.prb_usage:6.1f}%  ", end="")
                
                # Check for anomalies
                if detector:
                    is_anomaly, reason = detector.detect(record)
                    if is_anomaly:
                        print(f" ⚠️  ANOMALY: {reason}")
                    else:
                        print(" ✅ Normal")
                else:
                    print()
                
                print(f"  Throughput:     {record.throughput:6.1f} Mbps")
                print(f"  Latency:        {record.latency:6.1f} ms")
                print(f"  Packet Loss:    {record.packet_loss:6.2f}%")
                print(f"  Source:         {record.source}")
                
                if is_anomaly and detector:
                    stats = detector.get_statistics()
                    print(f"\n  📊 Anomaly Stats: {stats['total_records']} records, "
                          f"{stats['anomaly_count']} anomalies detected "
                          f"({stats['anomaly_rate']:.1f}%)")
            else:
                print(f"[{timestamp}] ❌ Failed to fetch KPI")
            
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("Monitor stopped by user")
        if detector:
            stats = detector.get_statistics()
            print(f"Final Statistics:")
            print(f"  Total Records: {stats['total_records']}")
            print(f"  Anomalies: {stats['anomaly_count']} ({stats['anomaly_rate']:.1f}%)")
        print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor Open5GS KPIs in real-time")
    parser.add_argument(
        "-i", "--interval",
        type=int,
        default=5,
        help="Update interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--no-anomaly",
        action="store_true",
        help="Disable anomaly detection"
    )
    
    args = parser.parse_args()
    
    monitor_open5gs(
        interval_seconds=args.interval,
        show_anomalies=not args.no_anomaly
    )
