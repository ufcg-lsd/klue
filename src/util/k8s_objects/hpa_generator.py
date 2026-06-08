import pandas as pd

class HPAGenerator: 
"""
Utility for generating Kubernetes HorizontalPodAutoscaler (HPA) manifests
from pandas DataFrame rows.

This class converts normalized row data into complete HPA YAML
structures and groups them by action: create, delete, or update.

Expected assumptions:
- CPU values come in cores.
- Memory values come in bytes.
- Each received row includes an `action` field indicating the intended operation.
"""
    def _normalize_metric_value(self, resource_name: str, metric_value: str, metric_type: str):
        if pd.isna(metric_value) or pd.isna(metric_type):
            return None

        value = metric_value.strip()
        metric_type = metric_type.strip().lower()

        if metric_type == "utilization":
            return int(float(value))

        return value
    
    def _build_metric_yaml(self, resource_name: str, metric_value: str, metric_type: str):
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
        if pd.isna(metric_value) or pd.isna(metric_type):
            return None

        metric_type = str(metric_type).strip().lower()
        normalized_value = self._normalize_metric_value(resource_name, str(metric_value), metric_type)

        if normalized_value is None:
            return None

        if metric_type == "utilization":
            target = {
                "type": "Utilization",
                "averageUtilization": normalized_value,
            }
        elif metric_type in {"average", "averagevalue"}:
            target = {
                "type": "AverageValue",
                "averageValue": normalized_value,
            }
        elif metric_type == "value":
            target = {
                "type": "Value",
                "value": normalized_value,
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

    def hpa_row_to_yaml(self, row_data: dict):
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
        name = row_data.get("horizontalpodautoscaler")
        namespace = row_data.get("namespace")

        if not name or not namespace:
            return None

        min_replicas = row_data.get("min_replicas")
        max_replicas = row_data.get("max_replicas")

        if pd.isna(max_replicas):
            return None
        
        metrics = [
            self._build_metric_yaml("cpu", row_data.get("cpu"), row_data.get("cpu_type")),
            self._build_metric_yaml("memory", row_data.get("memory"), row_data.get("memory_type")),
        ]
        metrics = [metric for metric in metrics if metric is not None]

        doc = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": name,
                },
                "maxReplicas": int(float(max_replicas))
            },
        }

        if pd.notna(min_replicas):
            doc["spec"]["minReplicas"] = int(float(min_replicas))

        if metrics:
            doc["spec"]["metrics"] = metrics

        return doc


    """
    Generate HPA payloads grouped by requested action.

    The input DataFrame is expected to contain one row per HPA definition,
    including an action column with one of the following values: 'apply' or 'delete'.

    Args:
        group: DataFrame containing HPA definitions and action metadata.

    Returns:
        A tuple containing:
        - applied_hpa_objects:
            Dictionary where keys are namespaces and values are lists of HPA manifests to create.
        - deleted_hpa_objects:
            List of dictionaries with name and namespace.
    """
    def generate_hpa_objects(self, group: pd.DataFrame):
        applied_hpa_objects = {}
        deleted_hpa_objects = []

        for row in group.itertuples():
            if row.action == 'apply':
                hpa_obj = self.hpa_row_to_yaml(row._asdict())
                if not hpa_obj: continue

                if row.namespace not in applied_hpa_objects:
                    applied_hpa_objects[row.namespace] = [hpa_obj]
                else:
                    applied_hpa_objects[row.namespace].append(hpa_obj)

            elif row.action == 'delete':
                deleted_hpa_objects.append({
                    "name": row.horizontalpodautoscaler,
                    "namespace": row.namespace,
                    "kind": "HorizontalPodAutoscaler"
                })
            
        return applied_hpa_objects, deleted_hpa_objects
