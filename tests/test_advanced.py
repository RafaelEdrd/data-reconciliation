import csv
import json
from pathlib import Path

import pytest

from reconciliation.cli import main
from reconciliation.config import load_config
from reconciliation.errors import ConfigurationError, OutputError
from reconciliation.history import collect, export_history
from reconciliation.matcher import reconcile
from reconciliation.readers import read_dataset


def test_composite_key_avoids_delimiter_collisions(tmp_path):
    mapping = {
        'version': 1, 'source': {}, 'target': {},
        'key': {'parts': [{'source': 'region', 'target': 'region'},
                          {'source': 'order', 'target': 'order'}]},
        'fields': [{'name': 'label', 'source': 'label', 'target': 'label', 'type': 'text'}],
    }
    path = tmp_path / 'mapping.json'
    path.write_text(json.dumps(mapping))
    config = load_config(path)
    left = tmp_path / 'left.csv'
    right = tmp_path / 'right.csv'
    left.write_text('region,order,label\n"a,b",c,ok\na,"b,c",ok\n', encoding='utf-8')
    right.write_text('region,order,label\na,"b,c",ok\n"a,b",c,ok\n', encoding='utf-8')
    needed = {'region', 'order', 'label'}
    result = reconcile(read_dataset(left, 'source', config.source, needed),
                       read_dataset(right, 'target', config.target, needed), config)
    assert result.counts['MATCHED'] == 2
    assert not result.differences


def test_absolute_tolerance_is_inclusive_and_exact(tmp_path):
    data = {
        'version': 1, 'source': {}, 'target': {},
        'key': {'source': 'id', 'target': 'id'},
        'fields': [{'name': 'money', 'source': 'value', 'target': 'value', 'type': 'decimal',
                    'source_format': {'decimal': '.'}, 'target_format': {'decimal': '.'},
                    'absolute_tolerance': '0.01'}],
    }
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(data))
    config = load_config(config_path)
    left, right = tmp_path / 'a.csv', tmp_path / 'b.csv'
    left.write_text('id,value\n1,0.01\n2,0.02000000000000000000001\n')
    right.write_text('id,value\n1,0.02\n2,0.04\n')
    result = reconcile(read_dataset(left, 'source', config.source, {'id', 'value'}),
                       read_dataset(right, 'target', config.target, {'id', 'value'}), config)
    assert result.counts['MATCHED'] == 1
    assert result.counts['MISMATCHED'] == 1
    assert result.tolerated_fields == {'money': 1}
    data['fields'][0]['absolute_tolerance'] = '-0.01'
    config_path.write_text(json.dumps(data))
    with pytest.raises(ConfigurationError):
        load_config(config_path)


def test_history_indexes_only_generated_manifests(example_paths, tmp_path):
    root = tmp_path / 'runs'
    reports = root / 'first'
    assert main(['compare', '--source', str(example_paths[0]), '--target', str(example_paths[1]),
                 '--config', str(Path(__file__).resolve().parents[1] / 'examples/mapping.json'),
                 '--output', str(reports)]) == 0
    output = tmp_path / 'trend.csv'
    assert export_history(root, output) == 1
    with output.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]['run'] == 'first'
    assert int(rows[0]['matched']) == 3
    with pytest.raises(OutputError):
        export_history(root, output)
    (root / 'bad').mkdir()
    (root / 'bad' / 'summary.json').write_text('{')
    with pytest.raises(OutputError):
        collect(root)
