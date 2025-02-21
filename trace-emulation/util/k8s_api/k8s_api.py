from kubernetes import client, config

class K8SAPI:
    def __init__(self):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.custom_api = client.CustomObjectsApi()

    # Nodes
    def list_node(self, **kwargs):
        return self.v1.list_node(**kwargs)
    
    def read_node(self, name, **kwargs):
        return self.v1.read_node(name=name, **kwargs)

    def patch_node(self, name, body, **kwargs):
        return self.v1.patch_node(name=name, body=body, **kwargs)

    # Namespaces
    def list_namespace(self, **kwargs):
        return self.v1.list_namespace(**kwargs)
    
    def read_namespace(self, name, **kwargs):
        return self.v1.read_namespace(name=name, **kwargs)

    def create_namespace(self, body, **kwargs):
        return self.v1.create_namespace(body=body, **kwargs)

    # Pods
    def list_pod_for_all_namespaces(self, **kwargs):
        return self.v1.list_pod_for_all_namespaces(**kwargs)

    # Deployments
    def read_namespaced_deployment(self, name, namespace, **kwargs):
        return self.apps_v1.read_namespaced_deployment(name=name, namespace=namespace, **kwargs)

    def create_namespaced_deployment(self, namespace, body, **kwargs):
        return self.apps_v1.create_namespaced_deployment(namespace=namespace, body=body, **kwargs)

    def patch_namespaced_deployment(self, name, namespace, body, **kwargs):
        return self.apps_v1.patch_namespaced_deployment(name=name, namespace=namespace, body=body, **kwargs)

    def patch_namespaced_deployment_scale(self, name, namespace, body, **kwargs):
        return self.apps_v1.patch_namespaced_deployment_scale(name=name, namespace=namespace, body=body, **kwargs)

    def delete_namespaced_deployment(self, name, namespace, **kwargs):
        return self.apps_v1.delete_namespaced_deployment(name=name, namespace=namespace, **kwargs)

    # StatefulSets
    def patch_namespaced_stateful_set_scale(self, name, namespace, body, **kwargs):
        return self.apps_v1.patch_namespaced_stateful_set_scale(name=name, namespace=namespace, body=body, **kwargs)

    # Custom Objects (Karpenter e outros CRDs)
    def create_cluster_custom_object(self, group, version, plural, body, **kwargs):
        return self.custom_api.create_cluster_custom_object(group=group, version=version, plural=plural, body=body, **kwargs)
    
    def get_cluster_custom_object(self, group, version, plural, name, **kwargs):
        return self.custom_api.get_cluster_custom_object(group=group, version=version, plural=plural, name=name, **kwargs)

    def list_cluster_custom_object(self, group, version, plural, **kwargs):
        return self.custom_api.list_cluster_custom_object(group=group, version=version, plural=plural, **kwargs)

    def patch_cluster_custom_object(self, group, version, plural, name, body, **kwargs):
        return self.custom_api.patch_cluster_custom_object(group=group, version=version, plural=plural, name=name, body=body, **kwargs)
