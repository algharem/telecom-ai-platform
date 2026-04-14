#!/usr/bin/env python3
"""Diagnostic script to analyze Open5GS log files and parser behavior"""

import sys
from pathlib import Path
import re
from collections import defaultdict

def analyze_log_structure(log_dir):
    """Analyze the structure of log files"""
    log_path = Path(log_dir)
    
    if not log_path.exists():
        print(f"ERROR: Log directory not found: {log_dir}")
        return
    
    print(f"Analyzing logs in: {log_path}")
    print("=" * 80)
    
    all_files = list(log_path.glob('*.log'))
    print(f"Found {len(all_files)} log files")
    
    for filepath in all_files:
        print(f"\n{filepath.name}:")
        print("-" * 40)
        
        # Sample first 20 lines
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [f.readline().strip() for _ in range(20)]
        
        # Analyze patterns
        patterns = defaultdict(int)
        cell_ids = set()
        imsis = set()
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                # Find cell IDs
                cell_match = re.search(r'[Cc]ell[_-]?[Ii][Dd]\s*[:\[=]\s*([0-9a-fx]+)', line)
                if cell_match:
                    cell_ids.add(cell_match.group(1))
                
                cell_match2 = re.search(r'\[([0-9a-fx]{4,})\].*[Cc]ell', line)
                if cell_match2:
                    cell_ids.add(cell_match2.group(1))
                
                # Find IMSI
                imsi_match = re.search(r'(?:IMSI|[0-9]{15})', line)
                if imsi_match:
                    imsis.add(imsi_match.group(0)[:15] if len(imsi_match.group(0)) >= 15 else imsi_match.group(0))
                
                # Categorize lines
                if 'attach' in line.lower() or 'registration' in line.lower():
                    patterns['attach/registration'] += 1
                elif 'session' in line.lower():
                    patterns['session'] += 1
                elif 'reject' in line.lower() or 'failure' in line.lower():
                    patterns['failure'] += 1
                elif 'error' in line.lower():
                    patterns['error'] += 1
                else:
                    patterns['other'] += 1
                
                if line_num >= 1000:  # Limit scan
                    break
        
        print(f"Lines scanned: {min(line_num, 1000)}")
        print(f"Pattern distribution: {dict(patterns)}")
        print(f"Unique cell IDs found: {len(cell_ids)}")
        if cell_ids:
            print(f"  Examples: {list(cell_ids)[:5]}")
        print(f"Unique IMSIs found: {len(imsis)}")
        
        # Show sample lines
        print("\nSample lines (first 5):")
        for line in lines[:5]:
            if line:
                print(f"  {line[:100]}...")

if __name__ == '__main__':
    log_dir = sys.argv[1] if len(sys.argv) > 1 else 'open5gs/log'
    analyze_log_structure(log_dir)
