from util.unique_reference import UniqueReferenceGenerator

class NodeGenerator:
    """
    A class responsible for generating Kubernetes Node objects,
    particularly for use with Kwok, based on instance data.
    """
    # Default versions and names as per the target YAML

    def __init__(self):
        """
        Initializes the NodeGenerator.
        """
        self.reference_generator = UniqueReferenceGenerator()

        self.KWOK_DEFAULT_KUBE_VERSION = "kwok-v0.7.0"

    def generate_node(self,
                      instance_type: str,
                      instance_data: dict,
                      instance_name: str,
                      ) -> dict:
        """
        Generates a Kubernetes Node object definition based on instance data.

        Args:
            instance_type (str): The name of the instance type. Expected to match
                                 instance_name["name"].
            instance_data (dict): Dictionary containing instance type details,
                                  including 'name', 'architecture', 'operatingSystems',
                                  and 'resources'.
            node_name (str, optional): The name of the node. If None,
                                       DEFAULT_NODE_NAME ("kwok-node") is used.
            custom_labels (dict, optional): Additional labels for the node.
            taints (list, optional): List of taints.
                                     If None, a default Kwok taint is applied.
                                     If an empty list, no taints are applied.

        Returns:
            dict: A dictionary representing the Node object, ready for YAML/JSON serialization.
        """

        instance_info = next((item for item in instance_data if item["name"] == instance_type), None)

        if not instance_info:
            return None
        
        resources = instance_info.get("resources", {})
        offerings = instance_info.get("offerings", [])

        if instance_name == None:
            instance_name = self.reference_generator.generate_name()

        architecture = instance_info.get("architecture", "amd64")
        os_list = instance_info.get("operatingSystems", ["linux"])
        os_type = os_list[0] if os_list else "linux"

        cpu_capacity = str(resources.get("cpu", "0"))
        memory_capacity = resources.get("memory", "0Gi")
        pods_capacity = str(resources.get("pods", "0"))
        ephemeral_storage_capacity = resources.get("ephemeral-storage", "0Gi")

        final_labels = {
            "eks-node-viewer/instance-price": str(next((o["Price"] for o in offerings if o["Available"]), "0")),
            "beta.kubernetes.io/arch": architecture,
            "beta.kubernetes.io/os": os_type,
            "kubernetes.io/arch": architecture,
            "kubernetes.io/hostname": instance_name,
            "kubernetes.io/os": os_type,
            "kwok.x-k8s.io/node": "true",
            "node.kubernetes.io/instance-type": instance_type,
        }

        kwok_annotations = {
            "kwok.x-k8s.io/node": "fake"
        }

        metadata = {
            "name": instance_name,
            "labels": final_labels,
            "annotations": kwok_annotations
        }

        kwok_taint = {
            "key": "kwok.x-k8s.io/node",
            "effect": "NoSchedule",
            "value": "fake"
        }

        spec = {
            "taints": [kwok_taint],
        }

        capacity_resources = {
            "cpu": cpu_capacity,
            "memory": memory_capacity,
            "pods": pods_capacity,
            "ephemeral-storage": ephemeral_storage_capacity
        }

        allocatable_resources = capacity_resources.copy()

        node_info = {
            "machineID": "",
            "systemUUID": "",
            "bootID": "",
            "kernelVersion": "",
            "osImage": "",
            "containerRuntimeVersion": "",
            "kubeletVersion": self.KWOK_DEFAULT_KUBE_VERSION,
            "kubeProxyVersion": self.KWOK_DEFAULT_KUBE_VERSION,
            "operatingSystem": os_type,
            "architecture": architecture
        }

        status = {
            "capacity": capacity_resources,
            "allocatable": allocatable_resources,
            "nodeInfo": node_info,
            "phase": "Running"
        }

        node_definition = {
            "apiVersion": "v1",
            "kind": "Node",
            "metadata": metadata,
            "spec": spec,
            "status": status
        }

        return node_definition