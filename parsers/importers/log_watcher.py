"""
Real-time log file watcher using inotify/watchdog.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class LogWatcher:
    """
    Watch Open5GS log files for changes and process new lines in real-time.
    
    Supports:
    - Multiple file watching
    - File rotation handling
    - Async callback processing
    """
    
    def __init__(self, 
                 log_directory: Path,
                 callback: Callable[[str, str], None],
                 file_patterns: Optional[Set[str]] = None):
        """
        Initialize log watcher.
        
        Args:
            log_directory: Directory containing log files
            callback: Async function(file_name, line) to call for new lines
            file_patterns: Set of file patterns to watch (e.g., {'amf.log', 'smf.log'})
        """
        self.log_dir = Path(log_directory)
        self.callback = callback
        self.file_patterns = file_patterns or {
            'amf.log', 'smf.log', 'upf.log', 'pcf.log', 'nrf.log'
        }
        
        self._running = False
        self._file_positions: dict = {}
        self._watch_tasks: list = []
    
    async def start(self):
        """Start watching log files"""
        self._running = True
        
        # Initialize file positions
        for pattern in self.file_patterns:
            log_file = self.log_dir / pattern
            if log_file.exists():
                self._file_positions[pattern] = log_file.stat().st_size
                logger.info(f"Watching {log_file} from position {self._file_positions[pattern]}")
        
        # Start watching tasks
        for pattern in self.file_patterns:
            task = asyncio.create_task(self._watch_file(pattern))
            self._watch_tasks.append(task)
        
        logger.info(f"Started watching {len(self._watch_tasks)} log files")
    
    def stop(self):
        """Stop watching"""
        self._running = False
    
    async def _watch_file(self, file_pattern: str):
        """Watch a single log file for changes"""
        log_file = self.log_dir / file_pattern
        
        while self._running:
            try:
                if not log_file.exists():
                    await asyncio.sleep(1)
                    continue
                
                current_size = log_file.stat().st_size
                last_pos = self._file_positions.get(file_pattern, 0)
                
                # File rotated or truncated
                if current_size < last_pos:
                    logger.info(f"Log file rotated: {file_pattern}")
                    last_pos = 0
                    self._file_positions[file_pattern] = 0
                
                # Read new content
                if current_size > last_pos:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_pos)
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    await self.callback(file_pattern, line)
                                except Exception as e:
                                    logger.error(f"Callback error for {file_pattern}: {e}")
                    
                    self._file_positions[file_pattern] = current_size
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error watching {file_pattern}: {e}")
                await asyncio.sleep(1)
    
    def get_status(self) -> dict:
        """Get current watcher status"""
        return {
            'running': self._running,
            'watched_files': list(self._file_positions.keys()),
            'positions': dict(self._file_positions)
        }
