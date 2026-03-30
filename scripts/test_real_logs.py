#!/usr/bin/env python3
"""
Test script to verify real Open5GS log parsing works correctly.
Demonstrates parsing the actual log files you provided.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.open5gs_real_parser import Open5GSRealLogParser, parse_open5gs_logs


def test_parse_individual_logs():
    """Test parsing individual log files"""
    
    print("=" * 70)
    print("Testing Individual Log File Parsing")
    print("=" * 70)
    
    parser = Open5GSRealLogParser()
    
    test_logs = {
        'test_logs/amf.log': 'amf',
        'test_logs/smf.log': 'smf',
        'test_logs/mme.log': 'mme',
        'test_logs/nrf.log': 'nrf',
    }
    
    for log_file, nf_type in test_logs.items():
        log_path = Path(log_file)
        
        if not log_path.exists():
            print(f"\n[SKIP] {log_file} - file not found")
            continue
        
        print(f"\n[PARSING] {log_file} ({nf_type})")
        events = parser.process_file(log_path, nf_type)
        
        print(f"  Total events extracted: {len(events)}")
        
        if events:
            # Show first 3 events
            for i, event in enumerate(events[:3]):
                print(f"  [{i+1}] {event.timestamp.isoformat()} | "
                      f"type={event.event_type} | "
                      f"imsi={event.imsi} | "
                      f"cell_id={event.cell_id}")
            
            if len(events) > 3:
                print(f"  ... and {len(events) - 3} more events")
        
        # Count event types
        event_types = {}
        for event in events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        print(f"  Event breakdown: {event_types}")


def test_aggregate_to_kpi():
    """Test aggregation to gNB-level KPIs"""
    
    print("\n" + "=" * 70)
    print("Testing Aggregation to gNB KPI Metrics")
    print("=" * 70)
    
    parser = Open5GSRealLogParser()
    
    # Parse all log files
    test_logs = {
        'test_logs/amf.log': 'amf',
        'test_logs/smf.log': 'smf',
        'test_logs/mme.log': 'mme',
    }
    
    all_events = []
    for log_file, nf_type in test_logs.items():
        log_path = Path(log_file)
        if log_path.exists():
            events = parser.process_file(log_path, nf_type)
            all_events.extend(events)
            print(f"[OK] Loaded {len(events)} events from {log_file}")
    
    print(f"\nTotal events: {len(all_events)}")
    
    # Aggregate to gNB metrics
    kpi_metrics = parser.aggregate_to_gnb_kpi(all_events)
    
    print(f"\ngNB Metrics Generated: {len(kpi_metrics)}")
    print("\n" + "-" * 70)
    
    for gnb_id in sorted(kpi_metrics.keys()):
        metric = kpi_metrics[gnb_id]
        print(f"\n{gnb_id}:")
        print(f"  PRB Usage:      {metric['prb_usage']:>6.2f}%")
        print(f"  Throughput:     {metric['throughput']:>6.2f} Mbps")
        print(f"  Latency:        {metric['latency']:>6.2f} ms")
        print(f"  Packet Loss:    {metric['packet_loss']:>6.2f}%")
        print(f"  Reg Success:    {metric['registration_success_rate']:>6.2f}%")
        print(f"  Session Count:  {metric['session_count']:>6.0f}")
        print(f"  Auth Failures:  {metric['auth_failures']:>6.0f}")
        print(f"  Attach Failures:{metric['attach_failures']:>6.0f}")


def test_main_parser():
    """Test the main parse_open5gs_logs() function"""
    
    print("\n" + "=" * 70)
    print("Testing Main Parser Function")
    print("=" * 70)
    
    log_dir = Path('test_logs')
    
    if not log_dir.exists():
        print(f"[SKIP] {log_dir} directory not found")
        return
    
    print(f"Parsing logs from: {log_dir.resolve()}")
    
    try:
        kpi_list = parse_open5gs_logs(log_dir)
        print(f"\n[SUCCESS] Generated {len(kpi_list)} gNB KPI records")
        
        if kpi_list:
            print("\nSample KPI Record:")
            sample = kpi_list[0]
            for key, value in sample.items():
                print(f"  {key:25s}: {value}")
        
        return kpi_list
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run all tests"""
    
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + "Real Open5GS Log Parser - Test Suite".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Test individual file parsing
    test_parse_individual_logs()
    
    # Test aggregation
    test_aggregate_to_kpi()
    
    # Test main function
    kpi_records = test_main_parser()
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    if kpi_records and len(kpi_records) > 0:
        print("[PASS] Log parsing successful!")
        print(f"       Generated {len(kpi_records)} gNB KPI records")
        print("\nYou can now use these logs in the API:")
        print("  1. Set DATA_SOURCE=logs")
        print("  2. Set LOG_BASE_PATH=/path/to/logs")
        print("  3. Restart the application")
        print("  4. Call /api/v1/ml/kpi/batch/from-data-source")
    else:
        print("[WARN] No KPI records generated")
        print("       Check that log files exist in test_logs/ directory")
    
    print("\n")


if __name__ == '__main__':
    main()
