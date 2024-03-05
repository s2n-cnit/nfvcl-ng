from __future__ import annotations

from typing import List

from pydantic import Field

from blueprints_ng.ansible_builder import AnsibleTask


class AnsibleVyOSConfigTask(AnsibleTask):
    lines: List[str] = Field(default=[])
    save: str = Field(default='yes')

class AnsibleVyOSStateGather(AnsibleTask):
    state: str = Field(default='gathered')


class VyOSNATRuleAlreadyPresent(Exception):
    pass

class VyOSNATRuleNotFound(Exception):
    pass
