def pytest_collection_modifyitems(items):
    """Modifies test items in place to ensure test classes run in a given order."""
    CLASS_ORDER = ["TestGroupTopology", "TestGroupK8s", "TestGroupUERANSIM", "TestGroup5G"]
    sorted_items = items.copy()
    # read the class names from default items
    class_mapping = {item: item.cls.__name__ for item in items}

    # Iteratively move tests of each class to the end of the test queue
    for class_ in CLASS_ORDER:
        sorted_items = [it for it in sorted_items if class_mapping[it] != class_] + [
            it for it in sorted_items if class_mapping[it] == class_
        ]

    items[:] = sorted_items


pytest_plugins = [
    "common_fixtures",
    "topology.test_topology",
    "blueprints.blue5g.context_5g",
]
