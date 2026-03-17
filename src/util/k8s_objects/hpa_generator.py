import pandas as pd

class HPAGenerator:
    def _build_metric_yaml(self, resource_name: str, metric_value: int | float, metric_type: str) -> dict | None:
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

    def generate_hpa_objects(self, group: pd.DataFrame) -> tuple[list, list, list]:
        new_hpa_objects = {}
        deleted_hpa_objects = []
        updated_hpa_objects = []

        for row in group.itertuples():
            if row.action == 'create':
                hpa_obj = self.hpa_row_to_yaml(row._asdict())

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

                updated_hpa_objects.append({
                    "action": "update-hpa",
                    "hpa_obj" : hpa_obj
                })
        
        return new_hpa_objects, deleted_hpa_objects, updated_hpa_objects
