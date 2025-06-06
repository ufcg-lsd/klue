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

def main():
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
        print(f"Uso: {sys.argv[0]} <trace_path> <nodepool_path> <karpenter-on/off> <skip-tracer/no-skip>")
        sys.exit(1)

    trace_path = sys.argv[1]
    nodepool_path = sys.argv[2]
    karpenter = True if (sys.argv[3] == "karpenter-on") else False
    tracer_skip = True if (sys.argv[4] == "skip-tracer") else False
    infrastructure = sys.argv[5]
    workload = sys.argv[6]

    # Executa o comando kubectl apply
    subprocess.run(["kubectl", "apply", "-f", nodepool_path])

    tracer = None
    if karpenter:
        tracer = TracerKarpenter(
            os.path.join(trace_path, "kube_pod_container_resource_requests.csv"),
            os.path.join(trace_path, "karpenter_pods_state.csv"),
            os.path.join(trace_path, "kube_pod_owner.csv"),
            os.path.join(trace_path, "kube_replicaset_owner.csv"),
            os.path.join(trace_path, "instance_types.json")
        )
    else:
        tracer = TracerKWOKOnly(
            os.path.join(trace_path, "kube_pod_container_resource_requests.csv"),
            os.path.join(trace_path, "container_cpu_usage_seconds_total.csv"),
            os.path.join(trace_path, "kube_pod_owner.csv"),
            os.path.join(trace_path, "kube_pod_status_phase.csv"),
            os.path.join(trace_path, "kube_replicaset_owner.csv"),
            os.path.join(trace_path, "instance_types.json")
        )

    # Executa o tracer.py
    if not tracer_skip:
        tracer.run()

    # Executa o broker.py
    manager = Manager(karpenter=karpenter, infrastructure=infrastructure, workload=workload)
    manager.run()

if __name__ == "__main__":
    main()
