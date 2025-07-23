"""
K8SObjectGenerator is a utility class for generating various Kubernetes objects,
including NodeClaims, Deployments, StatefulSets, and Jobs. It provides methods
to create these objects based on input data and group information, enabling
dynamic and automated Kubernetes resource management.
"""
import pandas as pd
from util.k8s_objects.nodeclaim_generator import NodeClaimGenerator
from util.k8s_objects.deployments_generator import DeploymentsGenerator
from util.k8s_objects.jobs_generator import JobsGenerator
from util.k8s_objects.statefulsets_generator import StatefulSetsGenerator
from util.k8s_objects.node_generator import NodeGenerator

class K8SObjectGenerator:
    
    def __init__(self, karpenter=True, cluster_autoscaler = False):
        self.nodeclaim_generator = NodeClaimGenerator()
        self.node_generator = NodeGenerator()
        self.deployments_generator = DeploymentsGenerator(karpenter=karpenter, cluster_autoscaler=cluster_autoscaler)
        self.statefulsets_generator = StatefulSetsGenerator()
        self.jobs_generator = JobsGenerator()
    
    def log(self, message):
        """
        Logs a message with a "[K8S OBJECT GENERATOR]" prefix.
        """
        print(f"[K8S OBJECT GENERATOR] {message}")
        
    def generate_nodeclaim(self, instance_name, instance_data, nodepool_name):
        nodeclaim = self.nodeclaim_generator.generate_nodeclaim(instance_name, instance_data, nodepool_name)

        if nodeclaim == None:
            self.log(f"Instância '{instance_name}' não encontrada.")
        
        return nodeclaim

    def generate_node(self, instance_type, instance_data, instance_name=None):
        node = self.node_generator.generate_node(instance_type, instance_data, instance_name)

        if node == None:
            self.log(f"Instância '{instance_type}' não encontrada.")
        
        return node
    
    def generate_deployments(self, group: pd.DataFrame):
        applied_deployments = self.deployments_generator.generate_applied_deployments(group)
        deleted_deployments = self.deployments_generator.generate_deleted_deployments(group)
        scaled_deployments = self.deployments_generator.generate_scaled_deployments(group)
        
        return applied_deployments, deleted_deployments, scaled_deployments
    
    def generate_jobs(self):
        # TODO
        pass
    
    def generate_statefulsets(self):
        # TODO
        pass