"""Explicit, version-bound test assembly; never discovers another checkout."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess


@dataclass(frozen=True)
class NativeIntegrationEnvironment:
    pds_root: Path
    pds_commit: str
    ads_root: Path
    ads_commit: str


REQUIRED_FILES = {
    'pds': ('src/product_intelligence/native_market_flow.py',
            'tools/run_native_market_flow.py', 'tools/run_operating_review_provider.py',
            '.agents/skills/pds-operating-review/SKILL.md'),
    'ads': ('application/v2_controlled_advisory_qingyun_relay.py',
            'application/v2_controlled_advisory_real_provider.py'),
}


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate integration manifest key')
        value[key] = item
    return value


def _git(root, *arguments):
    try:
        result = subprocess.run(['git', '-C', str(root), *arguments],
                                capture_output=True, text=True, encoding='utf-8',
                                timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError('Integration Git preflight unavailable or timed out') from error
    if result.returncode:
        raise ValueError('Integration dependency must be a readable Git checkout')
    return result.stdout.strip()


def load_environment(manifest_path):
    """Require exact source versions without weakening production root checks."""
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'),
                          object_pairs_hook=_unique_pairs)
    if (type(manifest) is not dict or set(manifest) != {'schema', 'pds', 'ads'}
            or manifest['schema'] != 'market-native-integration/v1'):
        raise ValueError('Unsupported integration manifest')
    checked = {}
    for role in ('pds', 'ads'):
        entry = manifest[role]
        if (type(entry) is not dict or set(entry) != {'root', 'commit'}
                or type(entry['root']) is not str or type(entry['commit']) is not str
                or re.fullmatch(r'[0-9a-f]{40}', entry['commit']) is None):
            raise ValueError(f'{role}: absolute root and full Git commit required')
        root = Path(entry['root'])
        if not root.is_absolute() or root.absolute() != root.resolve() or str(root).startswith(('\\\\', '//')):
            raise ValueError(f'{role}: local, non-linked absolute root required')
        if not root.is_dir() or not all((root / item).is_file() for item in REQUIRED_FILES[role]):
            raise ValueError(f'{role}: integration source files unavailable')
        if Path(_git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
            raise ValueError(f'{role}: root must be the checkout top level')
        if _git(root, 'rev-parse', 'HEAD') != entry['commit']:
            raise ValueError(f'{role}: Git commit differs from manifest')
        if _git(root, 'status', '--porcelain', '--untracked-files=all'):
            raise ValueError(f'{role}: use a clean checkout; preserve existing work separately')
        checked[role] = root
    if checked['ads'] != checked['pds'].parent / 'amazon_ads_optimizer':
        raise ValueError('ADS must be the actual sibling required by the PDS transport')
    return NativeIntegrationEnvironment(checked['pds'], manifest['pds']['commit'],
                                        checked['ads'], manifest['ads']['commit'])
