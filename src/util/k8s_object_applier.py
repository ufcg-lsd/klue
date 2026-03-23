from kubernetes import client
from util.k8s_api.k8s_api import K8SAPI

class KubernetesObjectApplier:
    def __init__(self, k8s_api: K8SAPI, hpa=False):
        """
        Inicializa a classe com a API do Kubernetes e uma função de log.
        """
        self.k8s_api = k8s_api
        self.hpa = hpa
    
    def log(self, message):
        """
        Logs a message with a "[KUBERNETES APPLIER]" prefix.
        """
        print(f"[KUBERNETES APPLIER] {message}")

    def apply_deployment(self, obj, namespace, name):
        """
        Aplica um objeto do tipo Deployment ao cluster.
        """
        try:
            self.k8s_api.read_namespaced_deployment(name, namespace)
            self.k8s_api.patch_namespaced_deployment(name, namespace, obj)
            self.log(f"[INFO] Deployment {name} updated in namespace {namespace}.")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                self.k8s_api.create_namespaced_deployment(namespace, obj)
                self.log(f"[INFO] Deployment {name} created in namespace {namespace}.")

    def apply_hpa(self, obj, namespace, name):
        try:
            self.k8s_api.read_namespaced_horizontal_pod_autoscaler(name, namespace)
            self.k8s_api.patch_namespaced_horizontal_pod_autoscaler(name, namespace, obj)
            self.log(f"[INFO] HorizontalPodAutoscaler {name} updated in namespace {namespace}.")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                self.k8s_api.create_namespaced_horizontal_pod_autoscaler(namespace, obj)
                self.log(f"[INFO] HorizontalPodAutoscaler {name} created in namespace {namespace}.")
            
    def apply_nodeclaim(self, obj, name):
        """
        Aplica um objeto do tipo NodeClaim ao cluster.
        """
        try:
            obj["metadata"].pop("resourceVersion", None)
            self.k8s_api.patch_infrastructure_object(obj, "karpenter.sh", "v1", "nodeclaims", name)
            self.log(f"[INFO] Nodeclaim {name} updated")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                obj["metadata"].pop("resourceVersion", None)
                self.k8s_api.create_infrastructure_object(obj, "karpenter.sh", "v1", "nodeclaims")
                self.log(f"[INFO] Nodeclaim {name} created")

    def apply_node(self, obj, name):
        """
        Aplica um objeto do tipo Node ao cluster.
        """
        obj.setdefault("metadata", {}).setdefault("annotations", {})
        obj["metadata"]["annotations"]["metrics.k8s.io/resource-metrics-path"] = (
            f"/metrics/nodes/{name}/metrics/resource"
        )

        try:
            obj["metadata"].pop("resourceVersion", None)
            self.k8s_api.patch_infrastructure_object(obj)
            self.log(f"[INFO] Node {name} updated")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                obj["metadata"].pop("resourceVersion", None)
                self.k8s_api.create_infrastructure_object(obj)
                self.log(f"[INFO] Node {name} created")

    def apply_service_monitor(self, obj, name):
        """
        Aplica um objeto do tipo ServiceMonitor ao cluster.
        """
        try:
            obj["metadata"].pop("resourceVersion", None)
            group="monitoring.coreos.com"
            version="v1"
            plural="servicemonitors"
            namespace="monitoring"
            self.k8s_api.patch_namespaced_custom_object(group=group, version=version, namespace=namespace, plural=plural, name=name, body=obj)
            self.log(f"[INFO] ServiceMonitor {name} updated")
        except client.exceptions.ApiException as e:
            if e.status == 404:
                obj["metadata"].pop("resourceVersion", None)
                self.k8s_api.create_namespaced_custom_object(group=group, version=version, namespace=namespace, plural=plural, body=obj)
                self.log(f"[INFO] ServiceMonitor {name} created")
            else:
                raise

    def apply_object(self, obj):
        """
        Aplica um objeto Kubernetes ao cluster, delegando para a função apropriada.
        """
        kind = obj.get("kind", "").lower()
        namespace = obj["metadata"].get("namespace", "default")
        name = obj["metadata"]["name"]

        if kind == "deployment":
            self.apply_deployment(obj, namespace, name)
        elif kind == "horizontalpodautoscaler" and self.hpa:
            self.apply_hpa(obj, namespace, name)
        elif kind == "nodeclaim":
            self.apply_nodeclaim(obj, name)
        elif kind == "node":
            self.apply_node(obj, name)
        else:
            self.log(f"[ERROR] Unsupported kind: {kind}")

    def delete_object(self, delete_info):
        """
        Deleta um objeto Kubernetes, delegando para a função apropriada.
        """
        kind = delete_info.get("kind", "Deployment").lower()
        name = delete_info["name"]
        namespace = delete_info.get("namespace", "default")

        if kind == "deployment":
            self.k8s_api.delete_namespaced_deployment(name, namespace)
            self.log(f"[INFO] Deployment {name} deleted in namespace {namespace}.")
        elif kind == "horizontalpodautoscaler" and self.hpa:
            self.k8s_api.delete_namespaced_horizontal_pod_autoscaler(name, namespace)
            self.log(f"[INFO] HorizontalPodAutoscaler {name} deleted in namespace {namespace}.")
        elif kind == "statefulset":
            self.k8s_api.delete_namespaced_stateful_set(name, namespace)
            self.log(f"[INFO] StatefulSet {name} deleted in namespace {namespace}.")
        else:
            self.log(f"[ERROR] Unsupported kind for deletion: {kind}")