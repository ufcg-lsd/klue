import sys
import os
import subprocess
from tracer import Tracer
from broker import Broker

def main():
    if len(sys.argv) < 3:
        print(f"Uso: {sys.argv[0]} <trace_path> <nodepool_path>")
        sys.exit(1)

    trace_path = sys.argv[1]
    nodepool_path = sys.argv[2]

    # Executa o comando kubectl apply
    subprocess.run(["kubectl", "apply", "-f", nodepool_path], check=True)

    tracer = Tracer(
        os.path.join(trace_path, "cenario4/kube_pod_container_resource_requests.csv"),
        os.path.join(trace_path, "cenario4/karpenter_pods_state.csv"),
        os.path.join(trace_path, "cenario4/kube_pod_owner.csv"),
        os.path.join(trace_path, "cenario4/kube_replicaset_owner.csv")
    )

    # Executa o tracer.py
    tracer.run()
    step = tracer.get_initial_input_step()

    # Executa o broker.py
    broker = Broker(input_step=step)
    broker.run()

if __name__ == "__main__":
    main()