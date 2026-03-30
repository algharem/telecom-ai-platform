#!/usr/bin/env python
"""
Example: Import Open5GS logs into AI Platform
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.open5gs_ingestor import Open5GSLogIngestor, import_open5gs_logs


async def example_batch_import():
    """Example: Batch import historical logs"""
    
    ingestor = Open5GSLogIngestor(
        log_directory=Path("/var/log/open5gs"),
        kafka_brokers="localhost:9092",
        year=2026
    )
    
    # Initialize parsers for AMF, SMF, UPF
    ingestor.initialize_parsers(['amf', 'smf', 'upf'])
    
    # Import last 24 hours
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)
    
    results = await ingestor.import_batch(
        nf_types=['amf', 'smf', 'upf'],
        start_time=start_time,
        end_time=end_time
    )
    
    print(f"Import complete: {results}")
    print(f"Correlation summary: {ingestor.get_correlation_summary()}")
    
    # Generate synthetic data based on patterns
    await ingestor.generate_synthetic_from_logs(
        output_file=Path("synthetic_from_patterns.csv"),
        duration_hours=168  # 1 week
    )


async def example_realtime_ingestion():
    """Example: Real-time log tailing"""
    
    ingestor = Open5GSLogIngestor(
        log_directory=Path("/var/log/open5gs"),
        kafka_brokers="localhost:9092"
    )
    
    ingestor.initialize_parsers(['amf', 'smf', 'upf'])
    
    # Start real-time tailing
    try:
        await ingestor.start_realtime_tailing(['amf', 'smf', 'upf'])
    except KeyboardInterrupt:
        await ingestor.stop()


async def example_quick_import():
    """Example: Quick one-line import"""
    
    results = await import_open5gs_logs(
        log_dir="/var/log/open5gs",
        kafka_brokers="kafka:9092",
        nf_types=["amf", "smf", "upf"]
    )
    
    print(f"Imported: {results}")


async def example_parse_and_analyze():
    """Example: Parse and analyze specific patterns"""
    
    from parsers.upf_parser import UPFParser
    
    # Parse UPF log
    parser = UPFParser(year=2026)
    
    events = list(parser.parse_file(Path("/var/log/open5gs/upf.log")))
    
    # Calculate throughput
    throughput_metrics = list(parser.calculate_throughput_metrics(
        iter(events),
        window_seconds=60
    ))
    
    print(f"Found {len(throughput_metrics)} throughput windows")
    for m in throughput_metrics[:5]:
        print(f"  {m['timestamp']}: {m['total_mbps']:.2f} Mbps "
              f"(UL: {m['ul_mbps']:.2f}, DL: {m['dl_mbps']:.2f})")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_batch_import())
    # asyncio.run(example_realtime_ingestion())
    # asyncio.run(example_quick_import())
    # asyncio.run(example_parse_and_analyze())