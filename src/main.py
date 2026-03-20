"""
This class is responsible for running a trace emulation process. It applies a Kubernetes 
node pool configuration, initializes a tracer to process trace data, and runs a broker 
to handle the emulation steps. The script interacts with Kubernetes and processes trace 
files to simulate cluster behavior.
"""
import sys
import os
import subprocess
from tracer.tracer_karpenter import TracerKarpenter
from tracer.tracer_kwok import TracerKWOKOnly
from manager import Manager

class Main:
    def __init__(self, trace_path, nodepool_path, karpenter, tracer_skip, infrastructure, workload):
        self.trace_path = trace_path
        self.nodepool_path = nodepool_path
        self.karpenter = karpenter
        self.tracer_skip = tracer_skip
        self.infrastructure = infrastructure
        self.workload = workload
    
    def apply_nodepool(self):
        """
        Applies the Kubernetes node pool configuration using kubectl apply.
        
        This method runs the command `kubectl apply -f <nodepool_path>` to apply the 
        specified node pool configuration to the Kubernetes cluster.
        """
        
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
        else:
            tracer = TracerKWOKOnly(
                os.path.join(self.trace_path, "kube_pod_container_resource_requests.csv"),
                os.path.join(self.trace_path, "container_cpu_usage_seconds_total.csv"),
                os.path.join(self.trace_path, "sum_container_cpu_usage_seconds_total.csv"),
                os.path.join(self.trace_path, "sum_container_memory_working_set_bytes.csv"),
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
        manager = Manager(karpenter=self.karpenter, infrastructure=self.infrastructure, workload=self.workload)
        manager.run()

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
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <data_path> <nodepool_path> <karpenter-on/off> <skip-tracer/no-skip> <infrastructure> <workload>")
        sys.exit(1)

    trace_path = sys.argv[1]
    nodepool_path = sys.argv[2]
    karpenter = True if (sys.argv[3] == "karpenter-on") else False
    tracer_skip = True if (sys.argv[4] == "skip-tracer") else False
    infrastructure = sys.argv[5]
    workload = sys.argv[6]

    main_instance = Main(trace_path, nodepool_path, karpenter, tracer_skip, infrastructure, workload)

    main_instance.apply_nodepool()

    main_instance.run_tracer()

    main_instance.run_manager()