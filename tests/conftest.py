"""Keep ordinary Market regression independent of external checkouts."""

import pytest

from tests.native_integration_environment import load_environment


def pytest_addoption(parser):
    group = parser.getgroup('Market native integration')
    group.addoption('--run-native-integration', action='store_true',
                    help='Run offline PDS/ADS integration against explicit pinned checkouts')
    group.addoption('--native-integration-manifest',
                    help='Local market-native-integration/v1 JSON with PDS/ADS roots and full commits')


def pytest_configure(config):
    selected = config.getoption('--run-native-integration')
    manifest = config.getoption('--native-integration-manifest')
    if selected != bool(manifest):
        raise pytest.UsageError('--run-native-integration and --native-integration-manifest must be supplied together')
    config.native_integration_environment = None
    if selected:
        try:
            config.native_integration_environment = load_environment(manifest)
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise pytest.UsageError(f'Native integration prerequisites not met: {error}') from error


def pytest_collection_modifyitems(config, items):
    if config.getoption('--run-native-integration'):
        return
    excluded = [item for item in items if item.get_closest_marker('native_integration')]
    if excluded:
        items[:] = [item for item in items if not item.get_closest_marker('native_integration')]
        config.hook.pytest_deselected(items=excluded)
    config.native_integration_deselected = len(excluded)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if config.getoption('--run-native-integration'):
        environment = config.native_integration_environment
        terminalreporter.write_line(f'Native integration selected: PDS {environment.pds_commit}; ADS {environment.ads_commit}; synthetic dependencies only.')
    elif getattr(config, 'native_integration_deselected', 0):
        count = config.native_integration_deselected
        terminalreporter.write_line(f'Native PDS/ADS integration NOT RUN: {count} deselected. Use --run-native-integration with --native-integration-manifest. Single-repository results do not qualify the cross-project flow.')


@pytest.fixture(scope='module')
def native_case(request):
    from tests.native_research_case import NativeResearchCase

    environment = request.config.native_integration_environment
    if environment is None:
        pytest.fail('Native integration was not explicitly configured')
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(environment.pds_root))
        patch.setenv('PYTHONDONTWRITEBYTECODE', '1')
        case = NativeResearchCase(environment.pds_root)
        def refuse_live_provider(*args, **kwargs):
            pytest.fail('Real Provider construction is forbidden in offline integration')
        patch.setattr(case.native.transport, 'provider_for', refuse_live_provider)
        yield case
