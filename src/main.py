"""
This class is responsible for running a trace emulation process. It applies a Kubernetes 
node pool configuration, initializes a tracer to process trace data, and runs a broker 
to handle the emulation steps. The script interacts with Kubernetes and processes trace 
files to simulate cluster behavior.
"""
import argparse
import sys
import os
import subprocess
from tracer.tracer_karpenter import TracerKarpenter
from tracer.tracer_kwok import TracerKWOKOnly
from tracer.tracer_cluster_autoscaler import TracerClusterAutoscaler
from manager import Manager

class Main:
    def __init__(self, trace_path, nodepool_path, karpenter, cluster_autoscaler, tracer_skip, infrastructure, workload, skip_pods_mapping, emulation_name = None, allocation_rule_path = None, speed_up_factor = None):
        self.trace_path = trace_path
        self.nodepool_path = nodepool_path
        self.karpenter = karpenter
        self.cluster_autoscaler = cluster_autoscaler
        self.tracer_skip = tracer_skip
        self.infrastructure = infrastructure
        self.workload = workload
        self.skip_pods_mapping = skip_pods_mapping
        self.emulation_name = emulation_name
        self.allocation_rule_path = allocation_rule_path
        self.speed_up_factor = speed_up_factor

    def apply_nodepool(self):
        """
        Applies the Kubernetes node pool configuration using kubectl apply.
        
        This method runs the command `kubectl apply -f <nodepool_path>` to apply the 
        specified node pool configuration to the Kubernetes cluster.
        """
        
        if self.nodepool_path is None:
            print("Node pool path is not specified. Skipping node pool application.")
            return
        subprocess.run(["kubectl", "apply", "-f", self.nodepool_path])

    def run_tracer(self):
        tracer = None
        if self.karpenter:
            tracer = TracerKarpenter(
                os.path.join(self.trace_path, "kube_pod_container_resource_requests.csv"),
                os.path.join(self.trace_path, "karpenter_pods_state.csv"),
                os.path.join(self.trace_path, "kube_pod_owner.csv"),
                os.path.join(self.trace_path, "kube_replicaset_owner.csv"),
                os.path.join(self.trace_path, "instance_types.json")
            )
        elif self.cluster_autoscaler:
            tracer = TracerClusterAutoscaler(
                os.path.join(self.trace_path, "kube_pod_container_resource_requests.csv"),
                os.path.join(self.trace_path, "container_cpu_usage_seconds_total.csv"),
                os.path.join(self.trace_path, "kube_pod_owner.csv"),
                os.path.join(self.trace_path, "kube_pod_status_phase.csv"),
                os.path.join(self.trace_path, "kube_replicaset_owner.csv"),
                os.path.join(self.trace_path, "instance_types.json"),
                self.allocation_rule_path
            )
        else:
            tracer = TracerKWOKOnly(
                os.path.join(self.trace_path, "kube_pod_container_resource_requests.csv"),
                os.path.join(self.trace_path, "container_cpu_usage_seconds_total.csv"),
                os.path.join(self.trace_path, "kube_pod_owner.csv"),
                os.path.join(self.trace_path, "kube_pod_status_phase.csv"),
                os.path.join(self.trace_path, "kube_replicaset_owner.csv"),
                os.path.join(self.trace_path, "instance_types.json")
            )

        # Executa o tracer.py
        if not self.tracer_skip:
            tracer.run()

    def run_manager(self):
        """
        Initializes and runs the Manager to handle the emulation process.
        This method creates an instance of the Manager class with the provided
        parameters and calls its run method to start the emulation.
        """
        # Executa o broker.py
        manager = Manager(karpenter=self.karpenter, infrastructure=self.infrastructure, workload=self.workload, skip_pods_mapping = self.skip_pods_mapping, emulation_name = self.emulation_name, speed_up_factor = self.speed_up_factor )
        manager.run()

def parse_arguments():
    """
    Parse command line arguments with proper defaults and validation.
    """
    parser = argparse.ArgumentParser(
        description="Execute trace emulation process",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("trace_path", help="Caminho do trace a ser usado na emulação")
    parser.add_argument("infrastructure", help="Tipo de infraestrutura (static/dynamic)")
    parser.add_argument("workload", help="Tipo de workload (static/dynamic)")
    
    parser.add_argument("--nodepool-path", 
                       help="Caminho do nodepool a ser usado na emulação")
    parser.add_argument("--karpenter", 
                       action="store_true", 
                       help="Ativar o Karpenter para gerenciamento de nós")
    parser.add_argument("--cluster-autoscaler", 
                       action="store_true", 
                       help="Ativar o Kubernetes Autoscaler para gerenciamento de nós")
    parser.add_argument("--skip-tracer", 
                       action="store_true", 
                       help="Pular a execução do tracer")
    parser.add_argument("--skip-pods-mapping", 
                       action="store_true", 
                       help="Pular a execução do pods mapping")
    parser.add_argument("--emulation-name", 
                       help="Nome da emulação")
    parser.add_argument("--allocation-rule", 
                       help="Caminho da regra de alocação a ser usada")
    parser.add_argument("--speed-up", 
                       type=int,
                       help="Fator de aceleração da emulação (ex: 2, 5, 10)")

    args = parser.parse_args()
    
    if not args.cluster_autoscaler and not args.nodepool_path:
        parser.error("--nodepool-path é obrigatório quando --cluster-autoscaler não está ativado")

    if args.karpenter and args.cluster_autoscaler:
        parser.error("Não é possível usar Karpenter e Kubernetes Cluster Autoscaler ao mesmo tempo")
    
    if args.speed_up and args.speed_up <= 0:
        parser.error("O fator de aceleração deve ser um número positivo")

    return args

if __name__ == "__main__":
    """
    Main function to execute the trace emulation process.

    This function performs the following steps:
    1. Validates the command-line arguments to ensure the required paths and options are provided.
    2. Applies the Kubernetes node pool configuration using `kubectl apply`.
    3. Initializes and runs the appropriate Tracer to process trace files.
    4. Optionally skips the tracer step based on user input.
    5. Initializes and runs the Manager to handle the emulation process.
    """

    args = parse_arguments()

    main_instance = Main(
        trace_path=args.trace_path,
        nodepool_path=args.nodepool_path,
        karpenter=args.karpenter,
        cluster_autoscaler=args.cluster_autoscaler,
        tracer_skip=args.skip_tracer,
        infrastructure=args.infrastructure,
        workload=args.workload,
        skip_pods_mapping=args.skip_pods_mapping,
        emulation_name=args.emulation_name,
        allocation_rule_path=args.allocation_rule,
        speed_up_factor=args.speed_up
    )

    main_instance.apply_nodepool()

    main_instance.run_tracer()

    main_instance.run_manager()