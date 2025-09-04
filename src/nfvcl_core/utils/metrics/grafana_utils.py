import re


def inject_label(promql_expr: str, label: str) -> str:
    """
    Injects a label into a PromQL expression if it is not already present.

    Args:
        promql_expr: The PromQL expression to be modified
        label: The label to inject into the expression

    Returns: The modified PromQL expression with the label injected
    """
    if label in promql_expr:
        return promql_expr  # Already added
    def replacer(match):
        inside = match.group(1).strip()
        if not inside:
            return "{" + label + "}"
        return "{" + inside + "," + label + "}"
    return re.sub(r'\{([^}]*)}', replacer, promql_expr)

def update_queries_in_panels(panels, label: str) -> None:
    """
    Recursively updates PromQL queries in a list of panels by injecting a label.

    Args:
        panels: The list of panels to update
        label: The label to inject into the PromQL expressions
    """
    for panel in panels:
        # Update targets
        targets = panel.get("targets", [])
        for target in targets:
            if "expr" in target:
                target["expr"] = inject_label(target["expr"], label)
        # Recurse into nested panels
        if "panels" in panel:
            update_queries_in_panels(panel["panels"], label)
        if panel.get("type") == "row" and "collapsed" in panel and panel["collapsed"]:
            update_queries_in_panels(panel.get("panels", []), label)

def replace_all_datasources(dashboard: dict, new_uid: str, new_type: str = "prometheus") -> None:
    """
    Replace all datasources in a Grafana dashboard with a new datasource.

    Args:
        dashboard: Dictionary representing the Grafana dashboard
        new_uid: The UID of the new datasource
        new_type: The type of the new datasource (default is "prometheus")

    """
    new_ds = {"uid": new_uid, "type": new_type}

    # 1. Replace panel-level and target-level datasources
    def replace_in_panels(panels: list):
        for panel in panels:
            if 'datasource' in panel:
                panel['datasource'] = new_ds
            if 'targets' in panel:
                for target in panel['targets']:
                    if 'datasource' in target:
                        target['datasource'] = new_ds
            # Recursively handle nested panels (rows or collapsible panels)
            if 'panels' in panel:
                replace_in_panels(panel['panels'])
            # Collapsed row-style panels
            if panel.get('type') == 'row' and panel.get('collapsed', False):
                replace_in_panels(panel.get('panels', []))

    replace_in_panels(dashboard.get("panels", []))

    # 2. Replace in templating variables
    templating_list = dashboard.get("templating", {}).get("list", [])
    for template in templating_list:
        if 'datasource' in template:
            template['datasource'] = new_ds

    # 3. Replace in annotations
    annotations = dashboard.get("annotations", {}).get("list", [])
    for annotation in annotations:
        if 'datasource' in annotation:
            annotation['datasource'] = new_ds
