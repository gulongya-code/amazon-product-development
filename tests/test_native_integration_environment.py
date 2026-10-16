"""Exercise version/setup failures without importing PDS or calling a Provider."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.native_integration_environment import REQUIRED_FILES, load_environment


ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def manifest(tmp_path):
    value = {'schema': 'market-native-integration/v1'}
    for role, name in (('pds', 'daily_data_auto_entry'), ('ads', 'amazon_ads_optimizer')):
        root = tmp_path / name
        root.mkdir()
        for relative in REQUIRED_FILES[role]:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# synthetic source marker only\n', encoding='utf8')
        git(root, 'init', '-q')
        git(root, 'add', '.')
        git(root, '-c', 'user.name=Market Fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic integration checkout')
        value[role] = {'root': str(root), 'commit': git(root, 'rev-parse', 'HEAD')}
    path = tmp_path / 'integration.json'
    path.write_text(json.dumps(value), encoding='utf8')
    return path, value


def save(path, value):
    path.write_text(json.dumps(value), encoding='utf8')


def test_explicit_clean_pinned_siblings_are_accepted(manifest):
    path, value = manifest
    environment = load_environment(path)
    assert environment.pds_root == Path(value['pds']['root'])
    assert environment.ads_commit == value['ads']['commit']


@pytest.mark.parametrize('role', ['pds', 'ads'])
def test_wrong_version_is_not_a_skipped_integration(manifest, role):
    path, value = manifest
    value[role]['commit'] = '0' * 40
    save(path, value)
    with pytest.raises(ValueError, match='Git commit differs'):
        load_environment(path)


@pytest.mark.parametrize('change', ['tracked', 'untracked'])
def test_modified_dependency_cannot_claim_exact_version(manifest, change):
    path, value = manifest
    root = Path(value['pds']['root'])
    target = root / (REQUIRED_FILES['pds'][0] if change == 'tracked' else 'untracked.py')
    target.write_text('# changed\n', encoding='utf8')
    with pytest.raises(ValueError, match='clean checkout'):
        load_environment(path)


def test_missing_ads_source_is_reported(manifest):
    path, value = manifest
    Path(value['ads']['root'], REQUIRED_FILES['ads'][0]).unlink()
    with pytest.raises(ValueError, match='ads: integration source files unavailable'):
        load_environment(path)


def test_short_or_relative_references_are_rejected(manifest):
    path, value = manifest
    value['pds']['root'] = 'relative-pds'
    save(path, value)
    with pytest.raises(ValueError, match='non-linked absolute root'):
        load_environment(path)
    value['pds']['root'] = str(path.parent / 'daily_data_auto_entry')
    value['pds']['commit'] = value['pds']['commit'][:7]
    save(path, value)
    with pytest.raises(ValueError, match='full Git commit required'):
        load_environment(path)


def test_linked_checkout_is_rejected_before_git(manifest):
    path, value = manifest
    alias = path.parent / 'pds-alias'
    try:
        alias.symlink_to(value['pds']['root'], target_is_directory=True)
    except OSError:
        if os.name != 'nt':
            raise
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), value['pds']['root']],
                       check=True, capture_output=True)
    value['pds']['root'] = str(alias)
    save(path, value)
    with pytest.raises(ValueError, match='non-linked absolute root'):
        load_environment(path)


def test_duplicate_manifest_keys_are_rejected(tmp_path):
    path = tmp_path / 'duplicate.json'
    path.write_text('{"schema":"market-native-integration/v1","pds":{},"pds":{}}', encoding='utf8')
    with pytest.raises(ValueError, match='Duplicate'):
        load_environment(path)


@pytest.mark.parametrize('arguments', [
    ['--run-native-integration'],
    ['--native-integration-manifest', 'missing.json'],
    ['--run-native-integration', '--native-integration-manifest', 'missing.json'],
])
def test_explicit_incomplete_setup_is_usage_error(arguments):
    result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '--collect-only', '-q',
                             '-p', 'no:cacheprovider', *arguments], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf8', timeout=30)
    assert result.returncode == 4
    assert ('must be supplied together' in result.stderr
            or 'prerequisites not met' in result.stderr)
    assert 'skipped' not in result.stdout


def test_default_collection_is_independent_and_discloses_excluded_cases():
    result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '--collect-only', '-q',
                             '-p', 'no:cacheprovider', 'tests/test_native_research_completion.py'],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf8', timeout=30)
    assert result.returncode == 5  # All 12 explicitly integration-only, not a passing run.
    assert '12 deselected' in result.stdout and 'integration NOT RUN' in result.stdout
    assert 'ModuleNotFoundError' not in result.stdout + result.stderr
