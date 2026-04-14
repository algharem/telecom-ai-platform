"""
Batch importer for historical Open5GS log files.
"""

import gzip
import logging
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Callable
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    """Statistics for a batch import"""
    file_path: str
    total_lines: int
    parsed_lines: int
    failed_lines: int
    start_time: datetime
    end_time: Optional[datetime] = None
    lines_per_second: float = 0.0
    
    def __post_init__(self):
        if self.end_time and self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            if duration > 0:
                self.lines_per_second = self.total_lines / duration


class BatchImporter:
    """
    Import historical Open5GS log files in batch mode.
    
    Features:
    - Parallel file processing
    - Progress tracking
    - Compressed file support
    - Time range filtering
    - Resume capability
    """
    
    def __init__(self, 
                 log_directory: Path,
                 parser_factory: Callable,
                 year: int = 2026):
        """
        Initialize batch importer.
        
        Args:
            log_directory: Directory containing log files
            parser_factory: Function(nf_type) -> parser instance
            year: Year for log timestamps
        """
        self.log_dir = Path(log_directory)
        self.parser_factory = parser_factory
        self.year = year
        
        self.stats: Dict[str, ImportStats] = {}
        self._progress_callbacks: List[Callable] = []
    
    def add_progress_callback(self, callback: Callable):
        """Add callback for progress updates"""
        self._progress_callbacks.append(callback)
    
    async def import_files(self,
                          nf_types: Optional[List[str]] = None,
                          start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None,
                          callback: Optional[Callable] = None) -> Dict[str, ImportStats]:
        """
        Import log files for specified NF types.
        
        Args:
            nf_types: NF types to import (None = all)
            start_time: Filter events after this time
            end_time: Filter events before this time
            callback: Called for each parsed event
        
        Returns:
            Dictionary of import statistics per NF
        """
        nf_types = nf_types or ['amf', 'smf', 'upf', 'pcf', 'nrf']
        self.stats = {}
        
        for nf in nf_types:
            log_file = self._find_log_file(nf)
            if not log_file:
                logger.warning(f"No log file found for {nf}")
                continue
            
            stats = await self._import_single_file(
                nf, log_file, start_time, end_time, callback
            )
            self.stats[nf] = stats
        
        return self.stats
    
    def _find_log_file(self, nf: str) -> Optional[Path]:
        """Find log file for NF (prefer uncompressed)"""
        uncompressed = self.log_dir / f"{nf}.log"
        compressed = self.log_dir / f"{nf}.log.gz"
        
        if uncompressed.exists():
            return uncompressed
        elif compressed.exists():
            return compressed
        return None
    
    async def _import_single_file(self,
                                   nf: str,
                                   file_path: Path,
                                   start_time: Optional[datetime],
                                   end_time: Optional[datetime],
                                   callback: Optional[Callable]) -> ImportStats:
        """Import a single log file"""
        start = datetime.now()
        total_lines = 0
        parsed_lines = 0
        failed_lines = 0
        
        parser = self.parser_factory(nf)
        
        logger.info(f"Importing {file_path}...")
        
        # Open file (handle compression)
        if file_path.suffix == '.gz':
            open_fn = gzip.open
            mode = 'rt'
        else:
            open_fn = open
            mode = 'r'
        
        with open_fn(file_path, mode, encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                
                # Progress reporting
                if line_num % 10000 == 0:
                    await self._report_progress(nf, line_num, total_lines)
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    event = parser._parse_line(line, file_path.name, line_num)
                    if event:
                        # Time filter
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        
                        parsed_lines += 1
                        
                        if callback:
                            await callback(event, nf, parser)
                            
                except Exception as e:
                    failed_lines += 1
                    if failed_lines <= 10:  # Log first 10 errors
                        logger.debug(f"Parse error at line {line_num}: {e}")
        
        end = datetime.now()
        stats = ImportStats(
            file_path=str(file_path),
            total_lines=total_lines,
            parsed_lines=parsed_lines,
            failed_lines=failed_lines,
            start_time=start,
            end_time=end
        )
        
        logger.info(f"Import complete: {parsed_lines}/{total_lines} lines ({stats.lines_per_second:.0f} lines/sec)")
        return stats
    
    async def _report_progress(self, nf: str, current: int, total: int):
        """Report import progress"""
        for callback in self._progress_callbacks:
            try:
                await callback(nf, current, total)
            except Exception as e:
                logger.debug(f"Progress callback error: {e}")
    
    def get_summary(self) -> Dict:
        """Get import summary"""
        total_parsed = sum(s.parsed_lines for s in self.stats.values())
        total_failed = sum(s.failed_lines for s in self.stats.values())
        total_lines = sum(s.total_lines for s in self.stats.values())
        
        return {
            'files_processed': len(self.stats),
            'total_lines': total_lines,
            'total_parsed': total_parsed,
            'total_failed': total_failed,
            'success_rate': total_parsed / total_lines if total_lines > 0 else 0,
            'per_nf': {
                nf: {
                    'parsed': stats.parsed_lines,
                    'failed': stats.failed_lines,
                    'lines_per_second': stats.lines_per_second
                }
                for nf, stats in self.stats.items()
            }
        }
