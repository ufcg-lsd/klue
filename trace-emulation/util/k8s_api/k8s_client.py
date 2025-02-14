from kubernetes import client, config

class K8SClient:
    def __init__(self):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
    
    def list_node(self):
        return self.v1.list_node()
    
    def list_pod_for_all_namespaces(self):
        return self.v1.list_pod_for_all_namespaces(watch=False)