import os
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--provider-config",
        action="store",
        default=os.getenv("NFVCL_PROVIDER_TEST_CONFIG"),
        help="Path to a provider integration test config YAML file.",
    )
    parser.addoption(
        "--run-provider-vim",
        action="store_true",
        default=os.getenv("NFVCL_RUN_PROVIDER_VIM_TESTS") == "1",
        help="Run direct provider tests against real VIMs from --provider-config.",
    )
    parser.addoption(
        "--run-provider-destructive",
        action="store_true",
        default=os.getenv("NFVCL_RUN_PROVIDER_DESTRUCTIVE_TESTS") == "1",
        help="Run provider tests that create/delete real VIM resources.",
    )


def pytest_collection_modifyitems(config, items):
    """Modifies test items in place to ensure test classes run in a given order."""
    CLASS_ORDER = ["TestGroupTopology", "TestGroupK8s", "TestGroupUERANSIM", "TestGroup5G"]
    sorted_items = items.copy()
    # read the class names from default items
    class_mapping = {item: item.cls.__name__ if item.cls is not None else "" for item in items}

    # Iteratively move tests of each class to the end of the test queue
    for class_ in CLASS_ORDER:
        sorted_items = [it for it in sorted_items if class_mapping[it] != class_] + [
            it for it in sorted_items if class_mapping[it] == class_
        ]

    items[:] = sorted_items

    provider_config = config.getoption("--provider-config")
    provider_config_exists = provider_config is not None and Path(provider_config).is_file()
    run_provider_vim = config.getoption("--run-provider-vim")
    run_provider_destructive = config.getoption("--run-provider-destructive")

    skip_provider_vim = pytest.mark.skip(
        reason="requires --run-provider-vim and --provider-config, or matching environment variables"
    )
    skip_provider_config = pytest.mark.skip(
        reason=f"provider config file not found: {provider_config}"
    )
    skip_provider_destructive = pytest.mark.skip(
        reason="requires --run-provider-destructive or NFVCL_RUN_PROVIDER_DESTRUCTIVE_TESTS=1"
    )

    for item in items:
        if "provider_vim" in item.keywords:
            if not run_provider_vim:
                item.add_marker(skip_provider_vim)
            elif not provider_config_exists:
                item.add_marker(skip_provider_config)
        if "provider_destructive" in item.keywords and not run_provider_destructive:
            item.add_marker(skip_provider_destructive)


pytest_plugins = [
    "tests.common_fixtures",
    "tests.topology.test_topology",
    "tests.blueprints.blue5g.context_5g",
]
