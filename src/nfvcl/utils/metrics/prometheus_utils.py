from typing import Dict


def create_prometheus_query(metric_name: str, labels: Dict[str, str]):
    labels_str = ', '.join([f'{k}="{v}"' for k, v in labels.items()])
    return f"{metric_name}{{{labels_str}}}"
