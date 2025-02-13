import pandas as pd
from util.k8s_objects.nodeclaim_generator import NodeClaimGenerator
from util.k8s_objects.deployments_generator import DeploymentsGenerator
from util.k8s_objects.jobs_generator import JobsGenerator
from util.k8s_objects.statefulsets_generator import StatefulSetsGenerator

class K8SObjectGenerator:
    
    def __init__(self):
        self.nodeclaim_generator = NodeClaimGenerator()
        self.deployments_generator = DeploymentsGenerator()
        self.statefulsets_generator = StatefulSetsGenerator()
        self.jobs_generator = JobsGenerator()
        
    def generate_nodeclaim(self, instance_name, instance_data, nodepool_name):
        nodeclaim = self.nodeclaim_generator.generate_nodeclaim(instance_name, instance_data, nodepool_name)

        if nodeclaim == None:
            print(f"Instância '{instance_name}' não encontrada.")
        
        return nodeclaim
    
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