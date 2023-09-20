from enum import Enum


class K8sEventType(Enum):
    PLUGIN_INSTALLED = "plugin_installed"
    DEFINITION_APPLIED = "definition_applied"
