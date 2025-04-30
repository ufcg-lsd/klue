"""
This class is responsible for running a trace emulation process. It applies a Kubernetes 
node pool configuration, initializes a tracer to process trace data, and runs a broker 
to handle the emulation steps. The script interacts with Kubernetes and processes trace 
files to simulate cluster behavior.
"""
import sys
import os
import subprocess
from tracer import Tracer
from broker import Broker

def main():
    """
    Main function to execute the trace emulation process.

    This function performs the following steps:
    1. Validates the command-line arguments to ensure the required paths are provided.
    2. Applies the Kubernetes node pool configuration using `kubectl apply`.
    3. Initializes and runs the `Tracer` to process trace files.
    4. Retrieves the initial input step from the tracer.
    5. Initializes and runs the `Broker` to handle the emulation process.
    """
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <trace_path> <nodepool_path>")
        sys.exit(1)

    trace_path = sys.argv[1]
    nodepool_path = sys.argv[2]

    # Executa o comando kubectl apply
    subprocess.run(["kubectl", "apply", "-f", nodepool_path], check=True)

    tracer = Tracer(
        os.path.join(trace_path, "kube_pod_container_resource_requests.csv"),
        os.path.join(trace_path, "karpenter_pods_state.csv"),
        os.path.join(trace_path, "kube_pod_owner.csv"),
        os.path.join(trace_path, "kube_replicaset_owner.csv")
    )

    # Executa o tracer.py
    tracer.run()
    step = tracer.get_initial_input_step()

    # Executa o broker.py
    broker = Broker(input_step=step)
    broker.run()

if __name__ == "__main__":
    main()
