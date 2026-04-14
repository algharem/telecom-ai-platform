#!/usr/bin/env python3
"""
Example: Import Open5GS logs into the AI Platform

Usage:
    # Batch import historical logs
    python examples/import_open5gs.py --batch --log-dir /var/log/open5gs
    
    # Real-time tailing
    python examples/import_open5gs.py --tail --log-dir /var/log/open5gs
    
    # Import specific NFs only
    python examples/import_open5gs.py --batch --nfs amf,upf --log-dir /var/log/open5gs
    
    # With time filter
    python examples/import_open5gs.py --batch --start "2026-03-27 00:00" --end "2026-03-27 23:59"
"""

import asyncio
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.open5gs_ingestor import Open5GSLogIngestor
from parsers.upf_parser import UPFParser
from parsers.amf_parser import AMFParser


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def batch_import(args):
    """Run batch import"""
    ingestor = Open5GSLogIngestor(
        log_directory=args.log_dir,
        kafka_brokers=args.kafka if not args.no_kafka else None,
        year=args.year
    )
    
    # Initialize parsers
    nf_types = args.nfs.split(',') if args.nfs else None
    ingestor.initialize_parsers(nf_types)
    
    # Parse time filters
    start_time = None
    end_time = None
    if args.start:
        start_time = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
    if args.end:
        end_time = datetime.strptime(args.end, "%Y-%m-%d %H:%M")
    
    # Run import
    counts = await ingestor.import_batch(
        nf_types=nf_types,
        start_time=start_time,
        end_time=end_time
    )
    
    # Print summary
    print("\n" + "="*50)
    print("BATCH IMPORT SUMMARY")
    print("="*50)
    for nf, count in counts.items():
        print(f"  {nf.upper()}: {count:,} events")
    print(f"\n  TOTAL: {sum(counts.values()):,} events")
    
    # Print correlation stats
    stats = ingestor.get_statistics()
    print(f"\n  Unique UEs: {stats['total_ues']}")
    print(f"  Unique gNBs: {stats['total_gnbs']}")
    
    await ingestor.close()


async def realtime_tail(args):
    """Run real-time tailing"""
    ingestor = Open5GSLogIngestor(
        log_directory=args.log_dir,
        kafka_brokers=args.kafka if not args.no_kafka else None,
        year=args.year
    )
    
    # Initialize parsers
    nf_types = args.nfs.split(',') if args.nfs else None
    ingestor.initialize_parsers(nf_types)
    
    print("\n" + "="*50)
    print("REAL-TIME LOG TAILING")
    print("="*50)
    print(f"  Log directory: {args.log_dir}")
    print(f"  NFs: {list(ingestor.parsers.keys())}")
    print(f"  Press Ctrl+C to stop\n")
    
    try:
        await ingestor.start_realtime_tailing(nf_types)
    except KeyboardInterrupt:
        print("\n\nStopping tailing...")
        ingestor.stop_tailing()
    
    # Print final stats
    stats = ingestor.get_statistics()
    print("\n" + "="*50)
    print("TAILING SUMMARY")
    print("="*50)
    print(f"  Unique UEs seen: {stats['total_ues']}")
    print(f"  Unique gNBs seen: {stats['total_gnbs']}")
    
    await ingestor.close()


async def demo_parsing(args):
    """Demo parsing without full platform"""
    log_file = Path(args.log_dir) / f"{args.demo_nf}.log"
    
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return
    
    print(f"\nParsing {log_file}...\n")
    
    # Select parser
    parsers = {
        'upf': UPFParser,
        'amf': AMFParser,
    }
    
    parser_cls = parsers.get(args.demo_nf)
    if not parser_cls:
        print(f"No parser available for {args.demo_nf}")
        return
    
    parser = parser_cls(year=args.year)
    
    count = 0
    kpi_count = 0
    
    for event in parser.parse_file(log_file):
        count += 1
        
        if args.verbose and count <= 10:
            print(f"[{event.nf_type}] {event.event_type}: {event.message[:100]}")
        
        kpi = parser.to_kpi_event(event)
        if kpi:
            kpi_count += 1
            if args.verbose and kpi_count <= 5:
                print(f"  -> KPI: {kpi.get('metric_type')}")
        
        if args.limit and count >= args.limit:
            break
    
    print(f"\nParsed {count} events, extracted {kpi_count} KPIs")


def main():
    parser = argparse.ArgumentParser(
        description='Import Open5GS logs into AI Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--log-dir', type=str, default='./open5gs_logs/log',
                       help='Directory containing Open5GS log files')
    parser.add_argument('--year', type=int, default=2026,
                       help='Year for log timestamps (default: 2026)')
    parser.add_argument('--nfs', type=str, default=None,
                       help='Comma-separated list of NFs to process (e.g., amf,smf,upf)')
    parser.add_argument('--kafka', type=str, default='localhost:9092',
                       help='Kafka broker address')
    parser.add_argument('--no-kafka', action='store_true',
                       help='Disable Kafka output')
    
    # Mode selection
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--batch', action='store_true',
                     help='Batch import historical logs')
    mode.add_argument('--tail', action='store_true',
                     help='Real-time log tailing')
    mode.add_argument('--demo', action='store_true',
                     help='Demo parsing without platform')
    
    # Batch options
    parser.add_argument('--start', type=str, default=None,
                       help='Start time filter (YYYY-MM-DD HH:MM)')
    parser.add_argument('--end', type=str, default=None,
                       help='End time filter (YYYY-MM-DD HH:MM)')
    
    # Demo options
    parser.add_argument('--demo-nf', type=str, default='upf',
                       choices=['upf', 'amf'],
                       help='NF to demo parse')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of events to parse')
    
    args = parser.parse_args()
    
    if args.batch:
        asyncio.run(batch_import(args))
    elif args.tail:
        asyncio.run(realtime_tail(args))
    elif args.demo:
        asyncio.run(demo_parsing(args))


if __name__ == '__main__':
    main()
