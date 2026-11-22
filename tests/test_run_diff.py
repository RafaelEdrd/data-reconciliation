import json
from pathlib import Path

import pytest

from reconciliation.errors import OutputError
from reconciliation.run_diff import compare_runs, write_comparison


def sample(tmp_path: Path, name: str, *, mapping='a'*64, matched=4):
    path = tmp_path / name
    path.write_text(json.dumps({
        'schema_version': 1, 'generated_at': '2026-01-01T00:00:00Z',
        'source': {'sha256': 'b'*64, 'rows': matched + 2},
        'target': {'sha256': 'c'*64, 'rows': matched + 1},
        'mapping_sha256': mapping,
        'counts': {'MATCHED': matched, 'MISMATCHED': 1, 'MISSING_SOURCE': 1,
                   'MISSING_TARGET': 0, 'DUPLICATE_KEY': 0, 'BLOCKED_KEY': 0,
                   'INVALID_RECORD': 0},
    }))
    return path


def test_compare_runs_discloses_population_and_count_changes(tmp_path):
    before = sample(tmp_path, 'before.json', matched=3)
    after = sample(tmp_path, 'after.json', matched=5)
    report = write_comparison(before, after, tmp_path / 'diff.json')
    assert report['counts']['MATCHED'] == {'before': 3, 'after': 5, 'delta': 2}
    assert report['rows']['source']['delta'] == 2
    assert report['comparable_mapping'] is True
    assert (tmp_path / 'diff.json').is_file()
    with pytest.raises(OutputError, match='already exists'):
        write_comparison(before, after, tmp_path / 'diff.json')


def test_changed_mapping_requires_opt_in(tmp_path):
    before = sample(tmp_path, 'before.json')
    after = sample(tmp_path, 'after.json', mapping='d'*64)
    with pytest.raises(OutputError, match='mapping changed'):
        compare_runs(before, after)
    report = compare_runs(before, after, allow_mapping_change=True)
    assert report['comparable_mapping'] is False


def test_bad_or_incomplete_manifest_is_refused(tmp_path):
    before = sample(tmp_path, 'before.json')
    invalid = tmp_path / 'bad.json'
    invalid.write_text('{"schema_version":1}')
    with pytest.raises(OutputError, match='invalid manifest'):
        compare_runs(before, invalid)
    invalid.write_text('garbled')
    with pytest.raises(OutputError):
        compare_runs(before, invalid)
