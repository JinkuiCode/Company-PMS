#!/usr/bin/env python3
"""Upgrade/restore copies only; the provided SQLite source is never written."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Register models without running application initialization or workers.
import app.models.init_db
from app.services.governance_rehearsal import rehearse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    rehearse(args.source, args.output_dir)
    print('源库未变更，升级副本及恢复副本均验证通过；正式数据库尚未升级')
