#!/usr/bin/env python3
"""
Test script for Prometheus integration.

Validates:
1. Prometheus connectivity
2. Open5GS metrics availability
3. Metric query functionality
4. KPI derivation logic
5. Full data provider integration
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from services.prometheus_client import PrometheusClient
from services.data_provider import PrometheusDataProvider, get_provider_config

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_prometheus_connectivity():
    """Test 1: Prometheus connectivity"""
    print("\n" + "="*70)
    print("TEST 1: Prometheus Connectivity")
    print("="*70)
    
    client = PrometheusClient(base_url="http://172.25.0.36:9090")
    
    is_available = client.is_available()
    print(f"Prometheus available: {is_available}")
    
    if not is_available:
        print("ERROR: Cannot connect to Prometheus at http://172.25.0.36:9090")
        return False
    
    print("SUCCESS: Prometheus is reachable")
    return True


def test_open5gs_metrics():
    """Test 2: Open5GS metrics availability"""
    print("\n" + "="*70)
    print("TEST 2: Open5GS Metrics Availability")
    print("="*70)
    
    client = PrometheusClient(base_url="http://172.25.0.36:9090")
    metrics = client.get_metric_names()
    
    print(f"Total metrics available: {len(metrics)}")
    
    # Check for Open5GS metrics
    open5gs_metrics = [m for m in metrics if 'fivegs' in m]
    print(f"Open5GS metrics found: {len(open5gs_metrics)}")
    
    if open5gs_metrics:
        print("\nSample Open5GS metrics:")
        for m in open5gs_metrics[:10]:
            print(f"  - {m}")
        return True
    else:
        print("ERROR: No Open5GS metrics found")
        return False


def test_metric_queries():
    """Test 3: Individual metric queries"""
    print("\n" + "="*70)
    print("TEST 3: Metric Queries")
    print("="*70)
    
    client = PrometheusClient(base_url="http://172.25.0.36:9090")
    
    queries = [
        ("fivegs_amffunction_rm_registeredsubnbr", "Registered UEs"),
        ("fivegs_smffunction_sm_sessionnbr", "PDU Sessions"),
        ("fivegs_upffunction_upf_sessionnbr", "UPF Sessions"),
    ]
    
    results = {}
    for query, label in queries:
        try:
            value = client.get_query_value(query)
            if value is not None:
                results[label] = value
                print(f"✓ {label}: {value}")
            else:
                print(f"✗ {label}: No value returned")
        except Exception as e:
            print(f"✗ {label}: Error - {e}")
    
    return len(results) > 0


def test_rate_queries():
    """Test 4: Rate metric queries"""
    print("\n" + "="*70)
    print("TEST 4: Rate Metric Queries")
    print("="*70)
    
    client = PrometheusClient(base_url="http://172.25.0.36:9090")
    
    rate_queries = [
        ("rate(fivegs_ep_n3_gtp_indatapktn3upf[5m])", "N3 In Rate"),
        ("rate(fivegs_ep_n3_gtp_outdatapktn3upf[5m])", "N3 Out Rate"),
        ("rate(fivegs_amffunction_amf_authfail[5m])", "Auth Fail Rate"),
    ]
    
    results = {}
    for query, label in rate_queries:
        try:
            value = client.get_query_value(query)
            if value is not None:
                results[label] = value
                print(f"✓ {label}: {value:.4f}")
            else:
                print(f"✗ {label}: No value returned")
        except Exception as e:
            print(f"✗ {label}: Error - {e}")
    
    return len(results) > 0


def test_kpi_derivation2():
    """Test 5: KPI derivation logic"""
    print("\n" + "="*70)
    print("TEST 5: KPI Derivation Logic")
    print("="*70)
    
    # Create sample metrics
    test_metrics = {
        'registered_ues': 5,
        'pdu_sessions': 8,
        'auth_requests': 100,
        'auth_fails': 2,
    }
    
    # Create provider with default config
    config = {
        "prometheus_url": "http://172.25.0.36:9090",
        "gnb_id": "gNB-001",
        "derivation": {
            "prb_base": 20.0,
            "prb_per_ue": 15.0,
            "mbps_per_session": 5.0,
            "latency_base_ms": 20.0,
            "latency_penalty_ms": 100.0
        }
    }
    
    provider = PrometheusDataProvider(config)
    kpis = provider._derive_kpis(test_metrics)
    
    print(f"Input metrics: {test_metrics}")
    print(f"\nDerived KPIs:")
    print(f"  PRB Usage: {kpis['prb_usage']}% (base=20%, +15% per UE: 20 + 5*15 = 95%)")
    print(f"  Throughput: {kpis['throughput']} Mbps (8 sessions * 5 Mbps)")
    print(f"  Latency: {kpis['latency']} ms (base=20ms + 2% failure * 100ms penalty)")
    print(f"  Packet Loss: {kpis['packet_loss']}% (2% failure rate * 100)")
    
    # Validate derivation
    expected_prb = min(100.0, 20.0 + 5 * 15.0)  # 95%
    expected_throughput = 8 * 5.0  # 40 Mbps
    expected_auth_rate = 2 / 100  # 0.02
    expected_latency = min(100.0, 20.0 + expected_auth_rate * 100.0)  # 22ms
    expected_loss = min(100.0, expected_auth_rate * 100.0)  # 2%
    
    success = (
        abs(kpis['prb_usage'] - expected_prb) < 0.1 and
        abs(kpis['throughput'] - expected_throughput) < 0.1 and
        abs(kpis['latency'] - expected_latency) < 0.1 and
        abs(kpis['packet_loss'] - expected_loss) < 0.1
    )
    
    if success:
        print("\n✓ KPI derivation logic is correct")
    else:
        print("\n✗ KPI derivation logic has issues")
    
    return success

# ---------------------------------
def test_kpi_derivation():
    """Test 5: KPI derivation logic"""
    print("\n" + "="*70)
    print("TEST 5: KPI Derivation Logic")
    print("="*70)
    
    # FIXED: Use internal keys that match PrometheusDataProvider logic
    test_metrics = {
        'amf_registered_ues': 5,    # Changed from 'registered_ues'
        'smf_pdu_sessions': 8,      # Changed from 'pdu_sessions'
        'amf_auth_req': 100,        # Changed from 'auth_requests'
        'amf_auth_fail': 2,         # Changed from 'auth_fails'
    }
    
    config = {
        "prometheus_url": "http://172.25.0.36:9090",
        "gnb_id": "gNB-001",
        "derivation": {
            "prb_base": 20.0,
            "prb_per_ue": 15.0,
            "mbps_per_session": 5.0,
            "latency_base_ms": 20.0,
            "latency_penalty_ms": 100.0
        }
    }
    
    provider = PrometheusDataProvider(config)
    kpis = provider._derive_kpis(test_metrics)
    
    print(f"Input metrics: {test_metrics}")
    print(f"\nDerived KPIs:")
    print(f"  PRB Usage: {kpis['prb_usage']}% (base=20%, +15% per UE: 20 + 5*15 = 95%)")
    print(f"  Throughput: {kpis['throughput']} Mbps (8 sessions * 5 Mbps)")
    print(f"  Latency: {kpis['latency']} ms (base=20ms + 2% failure * 100ms penalty)")
    print(f"  Packet Loss: {kpis['packet_loss']}% (2% failure rate * 100)")
    
    # Validate derivation
    expected_prb = min(100.0, 20.0 + 5 * 15.0)  # 95%
    expected_throughput = 8 * 5.0  # 40 Mbps
    expected_auth_rate = 2 / 100  # 0.02
    expected_latency = 20.0 + expected_auth_rate * 100.0  # 22ms
    expected_loss = expected_auth_rate * 100.0  # 2%
    
    success = (
        abs(kpis['prb_usage'] - expected_prb) < 0.1 and
        abs(kpis['throughput'] - expected_throughput) < 0.1 and
        abs(kpis['latency'] - expected_latency) < 0.1 and
        abs(kpis['packet_loss'] - expected_loss) < 0.1
    )
    
    if success:
        print("\n✓ KPI derivation logic is correct")
    else:
        print("\n✗ KPI derivation logic has issues")
    
    return success



# -------------
def test_provider_integration():
    """Test 6: Full PrometheusDataProvider integration"""
    print("\n" + "="*70)
    print("TEST 6: Full Provider Integration")
    print("="*70)
    
    # Get config
    env_config = {
        "PROMETHEUS_URL": "http://172.25.0.36:9090",
        "GNB_ID": "gNB-001"
    }
    
    config = get_provider_config("prometheus", env_config)
    print(f"Provider config:\n{config}\n")
    
    # Create provider
    provider = PrometheusDataProvider(config)
    print(f"Provider initialized: {provider}")
    print(f"Provider available: {provider.is_available()}")
    
    if not provider.is_available():
        print("WARNING: Provider not available (Prometheus metrics not found)")
        return False
    
    # Get batch
    batch = provider.get_next_batch(limit=1)
    
    if batch:
        record = batch[0]
        print(f"\nFetched KPI Record:")
        print(f"  Timestamp: {record.timestamp}")
        print(f"  gNB ID: {record.gnb_id}")
        print(f"  PRB Usage: {record.prb_usage}%")
        print(f"  Throughput: {record.throughput} Mbps")
        print(f"  Latency: {record.latency} ms")
        print(f"  Packet Loss: {record.packet_loss}%")
        print(f"  Source: {record.source}")
        
        # Validate ranges
        valid = (
            0 <= record.prb_usage <= 100 and
            record.throughput >= 0 and
            record.latency >= 0 and
            0 <= record.packet_loss <= 100 and
            record.source == "prometheus"
        )
        
        if valid:
            print("\n✓ KPI record is valid")
            return True
        else:
            print("\n✗ KPI record has invalid values")
            return False
    else:
        print("ERROR: No records returned from provider")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PROMETHEUS INTEGRATION TEST SUITE")
    print("="*70)
    
    tests = [
        ("Prometheus Connectivity", test_prometheus_connectivity),
        ("Open5GS Metrics", test_open5gs_metrics),
        ("Metric Queries", test_metric_queries),
        ("Rate Queries", test_rate_queries),
        ("KPI Derivation", test_kpi_derivation),
        ("Provider Integration", test_provider_integration),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}", exc_info=True)
            results[test_name] = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
