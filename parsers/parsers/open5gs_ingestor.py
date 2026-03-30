"""
Main coordinator for importing Open5GS logs into the AI platform.
Supports real-time tailing and batch historical import.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Callable
from datetime import datetime
import json

from parsers.base_parser import ParsedEvent, MetricsAggregator


logger = logging.getLogger(__name__)


class Open5GSLogIngestor:
    """
    Main coordinator for Open5GS log ingestion.
    
    Features:
    - Multi-NF log parsing
    - Real-time log tailing
    - Batch historical import
    - KPI extraction and streaming
    - Correlation across NFs
    """
    
    # NF to parser mapping
    PARSERS = {
        'amf': None,  # Lazy loaded
        'smf': None,
        'upf': None,
        'pcf': None,
    }
    
    def __init__(self, 
                 log_directory: Path,
                 kafka_brokers: Optional[str] = None,
                 year: int = 2026):
        self.log_dir = Path(log_directory)
        self.year = year
        
        # Initialize parsers
        self.parsers: Dict[str, object] = {}
        self.aggregators: Dict[str, MetricsAggregator] = {}
        
        # Streaming
        self.kafka = None
        if kafka_brokers:
            try:
                from streaming.producers import AsyncKafkaProducer
                self.kafka = AsyncKafkaProducer(kafka_brokers)
            except ImportError:
                logger.warning("Kafka producer not available, using local storage only")
        
        # Local storage
        self.db = None
        try:
            from infrastructure.database import InMemoryTimeSeriesDB
            self.db = InMemoryTimeSeriesDB()
        except ImportError:
            logger.warning("TimeSeriesDB not available, KPIs will only be logged")
            self.kpi_store: List[Dict] = []
        
        # Correlation storage
        self._ue_contexts: Dict[str, Dict] = {}  # IMSI -> context
        self._gnb_contexts: Dict[str, Dict] = {}  # gNB ID -> context
        
        self._running = False
    
    def initialize_parsers(self, nf_types: Optional[List[str]] = None):
        """Initialize parsers for specified NFs (or all available)"""
        nf_types = nf_types or ['amf', 'smf', 'upf', 'pcf']
        
        parser_classes = {
            'amf': ('parsers.amf_parser', 'AMFParser'),
            'smf': ('parsers.smf_parser', 'SMFParser'),
            'upf': ('parsers.upf_parser', 'UPFParser'),
            'pcf': ('parsers.pcf_parser', 'PCFParser'),
        }
        
        for nf in nf_types:
            if nf in parser_classes:
                module_name, class_name = parser_classes[nf]
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    parser_class = getattr(module, class_name)
                    self.parsers[nf] = parser_class(year=self.year)
                    self.aggregators[nf] = MetricsAggregator()
                    logger.info(f"Initialized parser for {nf.upper()}")
                except ImportError as e:
                    logger.warning(f"Could not initialize parser for {nf}: {e}")
    
    async def import_batch(self, 
                          nf_types: Optional[List[str]] = None,
                          start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None) -> Dict[str, int]:
        """
        Batch import historical logs.
        
        Returns counts per NF.
        """
        nf_types = nf_types or list(self.parsers.keys())
        counts = {nf: 0 for nf in nf_types}
        
        for nf in nf_types:
            if nf not in self.parsers:
                continue
            
            log_file = self.log_dir / f"{nf}.log"
            if not log_file.exists():
                log_file_gz = self.log_dir / f"{nf}.log.gz"
                if log_file_gz.exists():
                    log_file = log_file_gz
                else:
                    logger.warning(f"No log file found for {nf}")
                    continue
            
            logger.info(f"Importing {log_file}")
            
            parser = self.parsers[nf]
            aggregator = self.aggregators[nf]
            
            for event in parser.parse_file(log_file):
                # Time filter
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue
                
                # Process event
                await self._process_event(event, nf, parser)
                aggregator.add_event(event)
                counts[nf] += 1
            
            # Flush aggregated metrics
            for metrics in aggregator.get_metrics():
                await self._store_metrics(nf, metrics)
        
        logger.info(f"Batch import complete: {counts}")
        return counts
    
    async def start_realtime_tailing(self, nf_types: Optional[List[str]] = None):
        """
        Start real-time log tailing using asyncio.
        """
        self._running = True
        nf_types = nf_types or list(self.parsers.keys())
        
        tasks = []
        for nf in nf_types:
            if nf in self.parsers:
                task = asyncio.create_task(self._tail_log(nf))
                tasks.append(task)
        
        if not tasks:
            logger.warning("No parsers initialized for tailing")
            return
        
        await asyncio.gather(*tasks)
    
    def stop_tailing(self):
        """Stop real-time tailing"""
        self._running = False
    
    async def _tail_log(self, nf: str):
        """Tail single log file"""
        log_file = self.log_dir / f"{nf}.log"
        parser = self.parsers[nf]
        aggregator = self.aggregators[nf]
        
        if not log_file.exists():
            logger.error(f"Log file not found: {log_file}")
            return
        
        import subprocess
        
        process = subprocess.Popen(
            ['tail', '-F', '-n', '0', str(log_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"Started tailing {log_file}")
        
        try:
            while self._running:
                line = process.stdout.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                
                line = line.strip()
                if not line:
                    continue
                
                # Parse line
                try:
                    event = parser._parse_line(line, str(log_file), 0)
                    if event:
                        await self._process_event(event, nf, parser)
                        aggregator.add_event(event)
                except Exception as e:
                    logger.debug(f"Parse error in {nf} tail: {e}")
        finally:
            process.terminate()
            logger.info(f"Stopped tailing {log_file}")
    
    async def _process_event(self, 
                            event: ParsedEvent, 
                            nf_type: str, 
                            parser: object):
        """Process single parsed event"""
        
        # Update correlation contexts
        self._update_correlation_contexts(event)
        
        # Convert to KPI
        kpi = parser.to_kpi_event(event)
        if kpi:
            # Enrich with correlation data
            kpi = self._enrich_with_correlation(kpi, event)
            
            # Stream to Kafka
            if self.kafka:
                try:
                    await self.kafka.send(
                        topic="ran_metrics",
                        key=kpi.get('gnb_id', 'unknown'),
                        value=kpi
                    )
                except Exception as e:
                    logger.debug(f"Kafka send error: {e}")
            
            # Store locally
            await self._store_kpi(kpi)
        
        # Store raw event for debugging
        await self._store_raw_event(event)
    
    def _update_correlation_contexts(self, event: ParsedEvent):
        """Maintain UE and gNB context for correlation"""
        imsi = event.structured_data.get('imsi') or event.structured_data.get('supi')
        gnb_id = event.structured_data.get('gnb_id')
        
        if imsi:
            if imsi not in self._ue_contexts:
                self._ue_contexts[imsi] = {
                    'first_seen': event.timestamp,
                    'events': [],
                    'gnb_history': [],
                    'ip_addresses': set()
                }
            
            ctx = self._ue_contexts[imsi]
            ctx['last_seen'] = event.timestamp
            ctx['events'].append(event.event_type)
            
            # Keep only last 100 events to prevent memory leak
            if len(ctx['events']) > 100:
                ctx['events'] = ctx['events'][-100:]
            
            if gnb_id and gnb_id != 'unknown':
                ctx['gnb_history'].append({
                    'gnb_id': gnb_id,
                    'timestamp': event.timestamp
                })
                ctx['current_gnb'] = gnb_id
                
                # Keep only last 20 gNB changes
                if len(ctx['gnb_history']) > 20:
                    ctx['gnb_history'] = ctx['gnb_history'][-20:]
            
            if 'ue_ip' in event.structured_data:
                ctx['ip_addresses'].add(event.structured_data['ue_ip'])
        
        if gnb_id and gnb_id != 'unknown':
            if gnb_id not in self._gnb_contexts:
                self._gnb_contexts[gnb_id] = {
                    'first_seen': event.timestamp,
                    'ue_count': 0,
                    'events': []
                }
            
            self._gnb_contexts[gnb_id]['last_seen'] = event.timestamp
            self._gnb_contexts[gnb_id]['events'].append(event.event_type)
            
            # Keep only last 100 events
            if len(self._gnb_contexts[gnb_id]['events']) > 100:
                self._gnb_contexts[gnb_id]['events'] = self._gnb_contexts[gnb_id]['events'][-100:]
            
            # Update UE count for this gNB
            self._gnb_contexts[gnb_id]['ue_count'] = \
                len([ctx for ctx in self._ue_contexts.values() 
                     if ctx.get('current_gnb') == gnb_id])
    
    def _enrich_with_correlation(self, kpi: Dict, event: ParsedEvent) -> Dict:
        """Add correlation data to KPI"""
        imsi = kpi.get('imsi')
        
        if imsi and imsi in self._ue_contexts:
            ctx = self._ue_contexts[imsi]
            kpi['ue_session_duration'] = \
                (event.timestamp - ctx['first_seen']).total_seconds() if ctx.get('first_seen') else 0
            kpi['ue_handover_count'] = len(ctx['gnb_history']) - 1 if len(ctx['gnb_history']) > 1 else 0
        
        return kpi
    
    async def _store_kpi(self, kpi: Dict):
        """Store KPI to time-series database"""
        if self.db:
            try:
                from infrastructure.database import TimeSeriesRecord
                for field, value in kpi.items():
                    if isinstance(value, (int, float)) and field not in ['timestamp', 'gnb_id', 'imsi']:
                        record = TimeSeriesRecord(
                            timestamp=datetime.fromisoformat(kpi['timestamp']),
                            gnb_id=kpi.get('gnb_id', 'unknown'),
                            metric_name=f"kpi_{field}",
                            value=float(value),
                            tags={
                                'imsi': str(kpi.get('imsi', 'unknown')),
                                'dnn': str(kpi.get('dnn', 'default')),
                                'nf_source': kpi.get('metric_type', 'unknown').split('_')[0]
                            }
                        )
                        await self.db.write_kpi(record)
            except Exception as e:
                logger.debug(f"DB write error: {e}")
        else:
            # Fallback to local list
            if hasattr(self, 'kpi_store'):
                self.kpi_store.append(kpi)
    
    async def _store_metrics(self, nf_type: str, metrics: Dict):
        """Store aggregated metrics"""
        logger.debug(f"Aggregated metrics for {nf_type}: {metrics}")
    
    async def _store_raw_event(self, event: ParsedEvent):
        """Store raw event for debugging/replay"""
        # Optional: implement for debugging
        pass
    
    def get_ue_context(self, imsi: str) -> Optional[Dict]:
        """Get correlation context for a UE"""
        return self._ue_contexts.get(imsi)
    
    def get_gnb_context(self, gnb_id: str) -> Optional[Dict]:
        """Get correlation context for a gNB"""
        return self._gnb_contexts.get(gnb_id)
    
    def get_statistics(self) -> Dict:
        """Get ingestion statistics"""
        return {
            'total_ues': len(self._ue_contexts),
            'total_gnbs': len(self._gnb_contexts),
            'parsers_active': list(self.parsers.keys()),
            'ue_contexts': {
                imsi: {
                    'first_seen': ctx['first_seen'].isoformat() if ctx.get('first_seen') else None,
                    'last_seen': ctx.get('last_seen').isoformat() if ctx.get('last_seen') else None,
                    'current_gnb': ctx.get('current_gnb'),
                    'event_count': len(ctx.get('events', []))
                }
                for imsi, ctx in self._ue_contexts.items()
            },
            'gnb_contexts': {
                gnb_id: {
                    'ue_count': ctx.get('ue_count', 0),
                    'event_count': len(ctx.get('events', []))
                }
                for gnb_id, ctx in self._gnb_contexts.items()
            }
        }
    
    async def close(self):
        """Cleanup resources"""
        self.stop_tailing()
        if self.kafka:
            await self.kafka.close()
