import yaml
import subprocess
from datetime import datetime, timezone
from util.unique_reference import UniqueReferenceGenerator

class NodeClaimGenerator:
    def __init__(self):
        self.reference_generator = UniqueReferenceGenerator()

    def get_nodepool_info(self, nodepool_name, instance_name):
        try:
            result = subprocess.run(
                ["kubectl", "get", "nodepool", nodepool_name, "-o", "yaml"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            nodepool_data = yaml.safe_load(result.stdout)
            nodepool_info = {
                "disruption": nodepool_data.get("spec", {}).get("disruption", {}),
                "limits": nodepool_data.get("spec", {}).get("limits", {}),
                "requirements": nodepool_data.get("spec", {}).get("template", {}).get("spec", {}).get("requirements", []),
                "nodeClassRef": nodepool_data.get("spec", {}).get("template", {}).get("spec", {}).get("nodeClassRef", {}),
                "expireAfter": nodepool_data.get("spec", {}).get("template", {}).get("spec", {}).get("expireAfter", "720h"),
                "nodepool_hash": nodepool_data.get("metadata", {}).get("annotations", {}).get("karpenter.sh/nodepool-hash", "N/A"),
                "nodepool_hash_version": nodepool_data.get("metadata", {}).get("annotations", {}).get("karpenter.sh/nodepool-hash-version", "N/A"),
                "uid": nodepool_data.get("metadata", {}).get("uid"),
                "generation": nodepool_data.get("metadata", {}).get("generation"),
                "resourceVersion": nodepool_data.get("metadata", {}).get("resourceVersion"),
                "taints": nodepool_data.get("spec", {}).get("template", {}).get("spec", {}).get("taints", [])
            }
            
            nodepool_info["requirements"] = [
                requirement for requirement in nodepool_info["requirements"]
                if requirement.get("key") != "node.kubernetes.io/instance-type"
            ]
            
            nodepool_info["requirements"].append({
                'key': 'node.kubernetes.io/instance-type',
                'operator': 'In',
                'values': [instance_name]
            })
            
            # Extrai a arquitetura (kubernetes.io/arch) com valor padrão 'arm64' se não estiver presente
            architecture = next(
                (req["values"][0] for req in nodepool_info["requirements"] if req.get("key") == "kubernetes.io/arch"),
                "amd64"
            )
            nodepool_info["architecture"] = architecture
                
            return nodepool_info
        except subprocess.CalledProcessError as e:
            print(f"Erro ao executar kubectl: {e.stderr}")
            return None

    def generate_nodeclaim(self, instance_name, instance_data, nodepool_name):
        nodepool_info = self.get_nodepool_info(nodepool_name, instance_name)
        instance_info = next((item for item in instance_data if item["name"] == instance_name), None)
        
        if not instance_info:
            return None
        
        nodeclaim_name = self.reference_generator.generate_name()
        uid = self.reference_generator.generate_uuid()
        
        resources = instance_info.get("resources", {})
        offerings = instance_info.get("offerings", [])
        
        taints = nodepool_info["taints"]
        
        nodeclaim = {
            "apiVersion": "karpenter.sh/v1",
            "kind": "NodeClaim",
            "metadata": {
                "generateName": f"{nodepool_name}-",
                "annotations": {
                    "karpenter.sh/nodepool-hash": nodepool_info["nodepool_hash"],
                    "karpenter.sh/nodepool-hash-version": nodepool_info["nodepool_hash_version"],
                    "kwok.x-k8s.io/node": "fake"
                },
                "creationTimestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "finalizers": [
                    "karpenter.sh/termination"
                ],
                "generation": nodepool_info["generation"],
                "labels": {
                    "eks-node-viewer/instance-price": str(next((o["Price"] for o in offerings if o["Available"]), "0")),
                    "karpenter.kwok.sh/instance-cpu": resources.get("cpu", "N/A"),
                    "karpenter.kwok.sh/instance-family": instance_name.split(".")[0],
                    "karpenter.kwok.sh/instance-size": instance_name.split(".")[1],
                    "karpenter.kwok.sh/instance-memory": resources.get("memory", "N/A"),
                    "karpenter.sh/capacity-type": "on-demand",
                    "karpenter.sh/nodepool": nodepool_name,
                    "kubernetes.io/arch": nodepool_info["architecture"],
                    "kubernetes.io/hostname": nodeclaim_name,
                    "kubernetes.io/os": instance_info["operatingSystems"][0],
                    "kwok-partition": "a",
                    "kwok.x-k8s.io/node": "fake",
                    "node.kubernetes.io/instance-type": instance_name,
                    "topology.kubernetes.io/zone": "test-zone-d"
                },
                "name": nodeclaim_name,
                "ownerReferences": [
                    {
                        "apiVersion": "karpenter.sh/v1",
                        "blockOwnerDeletion": True,
                        "kind": "NodePool",
                        "name": nodepool_name,
                        "uid": nodepool_info["uid"]
                    }
                ],
                "resourceVersion": nodepool_info["resourceVersion"],
                "uid": uid
            },
            "spec": {
                "expireAfter": nodepool_info["expireAfter"],
                "nodeClassRef": nodepool_info["nodeClassRef"],
                "requirements": nodepool_info["requirements"],
                "taints": taints,
                "resources": {
                    "requests": {
                        "cpu": resources.get("cpu", "N/A"),
                        "memory": resources.get("memory", "N/A"),
                        "ephemeral-storage": resources.get("ephemeral-storage", "N/A"),
                        "pods": resources.get("pods", "N/A")
                    }
                },
            },
            "status": {
                "allocatable": {
                    "cpu": resources.get("cpu", "N/A"),
                    "memory": resources.get("memory", "N/A"),
                    "ephemeral-storage": resources.get("ephemeral-storage", "150Gi"),
                    "pods": resources.get("pods", "192")
                },
                "capacity": {
                    "cpu": resources.get("cpu", "N/A"),
                    "memory": resources.get("memory", "N/A"),
                    "ephemeral-storage": resources.get("ephemeral-storage", "150Gi"),
                    "pods": resources.get("pods", "192")
                },
                "conditions": [
                    {
                        "lastTransitionTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "message": "",
                        "observedGeneration": 1,
                        "reason": "ConsistentStateFound",
                        "status": "True",
                        "type": "ConsistentStateFound"
                    },
                    {
                        "lastTransitionTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "message": "",
                        "observedGeneration": 1,
                        "reason": "Ready",
                        "status": "True",
                        "type": "Ready"
                    }
                ]
            }
        }
        
        for offering in offerings:
            if offering["Available"]:
                for requirement in offering["Requirements"]:
                    requirement_dict = {
                        "key": requirement["key"],
                        "operator": requirement["operator"],
                        "values": requirement["values"]
                    }
                    nodeclaim["spec"]["requirements"].append(requirement_dict)
                break
        
        return nodeclaim