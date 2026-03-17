import pandas as pd

"""
Utility for generating Kubernetes HorizontalPodAutoscaler (HPA) manifests
from pandas DataFrame rows.

This class converts normalized row data into complete HPA YAML
structures and groups them by action: create, delete, or update.

Expected assumptions:
- Input rows already contain converted data types.
- CPU values are already normalized (for example, in millicores when applicable).
- Memory values are already normalized (for example, in bytes when applicable).
- Each received row includes an `action` field indicating the intended operation.
"""
class HPAGenerator:
    """
    Build the HPA metric block for a single resource.

    Supports Kubernetes resource metrics for CPU and memory only.

    Args:
        resource_name: Resource name used by the HPA metric, such as "cpu" or "memory".
        metric_value: Target value for the metric.
        metric_type: Metric target type, such as utilization, average or value.

    Returns:
        A dictionary representing the metric block in the HPA spec.
    """
    def _build_metric_yaml(self, resource_name: str, metric_value: str, metric_type: str) -> dict | None:
        if pd.isna(metric_value) or pd.isna(metric_type):
            return None

        metric_type = metric_type.strip().lower()

        if metric_type == "utilization":
            target = {
                "type": "Utilization",
                "averageUtilization": metric_value,
            }
        elif metric_type in {"average", "averagevalue"}:
            target = {
                "type": "AverageValue",
                "averageValue": metric_value,
            }
        elif metric_type == "value":
            target = {
                "type": "Value",
                "value": metric_value,
            }
        else:
            return None

        return {
            "type": "Resource",
            "resource": {
                "name": resource_name,
                "target": target,
            },
        }

    """
    Convert a single row of HPA data into a Kubernetes HPA manifest.

    Required fields:
    - horizontalpodautoscaler
    - namespace

    Optional fields:
    - min_replicas
    - max_replicas
    - cpu / cpu_type
    - memory / memory_type

    Args:
        row_data: Dictionary containing the HPA row data.

    Returns:
        A dictionary representing the HPA manifest.
    """
    def hpa_row_to_yaml(self, row_data: dict) -> dict | None:
        name = row_data.get("horizontalpodautoscaler")
        namespace = row_data.get("namespace")

        if not name or not namespace:
            return None

        min_replicas = row_data.get("min_replicas")
        max_replicas = row_data.get("max_replicas")

        metrics = [
            self._build_metric_yaml("cpu", row_data.get("cpu"), row_data.get("cpu_type")),
            self._build_metric_yaml("memory", row_data.get("memory"), row_data.get("memory_type")),
        ]
        metrics = [metric for metric in metrics if metric is not None]

        doc = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                }
            },
        }

        doc["metadata"]["name"] = name
        doc["spec"]["scaleTargetRef"]["name"] = name

        doc["metadata"]["namespace"] = namespace

        if pd.notna(min_replicas):
            doc["spec"]["minReplicas"] = min_replicas

        if pd.notna(max_replicas):
            doc["spec"]["maxReplicas"] = max_replicas

        if metrics:
            doc["spec"]["metrics"] = metrics

        return doc


    """
    Generate HPA payloads grouped by requested action.

    The input DataFrame is expected to contain one row per HPA definition,
    including an action column with one of the following values: 'create', 'update' or 'delete'.


    Args:
        group: DataFrame containing HPA definitions and action metadata.

    Returns:
        A tuple containing:
        - new_hpa_objects:
            Dictionary where keys are namespaces and values are lists of HPA manifests to create.
        - deleted_hpa_objects:
            List of dictionaries with name and namespace.
        - updated_hpa_objects:
            List of dictionaries containing the update action and the updated HPA manifest.
    """
    def generate_hpa_objects(self, group: pd.DataFrame) -> tuple[list, list, list]:
        new_hpa_objects = {}
        deleted_hpa_objects = []
        updated_hpa_objects = []

        for row in group.itertuples():
            if row.action == 'create':
                hpa_obj = self.hpa_row_to_yaml(row._asdict())
                if not hpa_obj: continue

                if row.namespace not in new_hpa_objects:
                    new_hpa_objects[row.namespace] = [hpa_obj]
                else:
                    new_hpa_objects[row.namespace].append(hpa_obj)

            elif row.action == 'delete':
                deleted_hpa_objects.append({
                    "name": row.name,
                    "namespace": row.namespace
                })
            
            elif row.action == 'update':
                hpa_obj = self.hpa_row_to_yaml(row._asdict())
                if not hpa_obj: continue

                updated_hpa_objects.append({
                    "action": "update-hpa",
                    "hpa_obj" : hpa_obj
                })
        
        return new_hpa_objects, deleted_hpa_objects, updated_hpa_objects
