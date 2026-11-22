"""Reproducible synthetic benchmark for the current in-memory reconciliation engine.

This is a measurement harness, not a claim about production throughput.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

from reconciliation.cli import main


def benchmark(rows: int) -> dict:
    if not 1 <= rows <= 500_000:
        raise ValueError('Rows must be between 1 and 500000')
    with tempfile.TemporaryDirectory(prefix='reconcile-benchmark-') as folder:
        root = Path(folder)
        source = root / 'source.csv'
        target = root / 'target.csv'
        mapping = root / 'mapping.json'
        mapping.write_text(json.dumps({
            'version': 1, 'source': {}, 'target': {},
            'key': {'source': 'id', 'target': 'id'},
            'fields': [{'name': 'amount', 'source': 'amount', 'target': 'amount',
                        'type': 'decimal', 'source_format': {'decimal': '.'},
                        'target_format': {'decimal': '.'}}],
        }), encoding='utf-8')
        with source.open('w', encoding='utf-8') as left, target.open('w', encoding='utf-8') as right:
            left.write('id,amount\n')
            right.write('id,amount\n')
            for idx in range(rows):
                amount = f'{idx % 997}.00'
                left.write(f'{idx:08d},{amount}\n')
                right.write(f'{idx:08d},{"0.00" if idx % 1000 == 7 else amount}\n')
        tracemalloc.start()
        start = time.perf_counter()
        exit_code = main(['compare', '--source', str(source), '--target', str(target),
                          '--config', str(mapping), '--output', str(root / 'report')])
        duration = time.perf_counter() - start
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if exit_code != 0:
            raise RuntimeError(f'Benchmark reconcile failed: {exit_code}')
        summary = json.loads((root / 'report' / 'summary.json').read_text())
        if summary['counts']['MATCHED'] + summary['counts']['MISMATCHED'] != rows:
            raise RuntimeError('Unexpected comparison counts')
        return {'rows_per_side': rows, 'seconds': round(duration, 3),
                'peak_tracemalloc_mib': round(peak_bytes / (1024 ** 2), 2),
                'mismatched': summary['counts']['MISMATCHED'],
                'note': 'tracemalloc measures Python allocations, not full process RSS'}


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=10000)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.rows), indent=2))


if __name__ == '__main__':
    run()
