#!/bin/bash

CURRENT_PATH=$(pwd)

kubectl apply -f "$CURRENT_PATH/data/nodepools.yaml"

python3 trace_setup.py "$CURRENT_PATH/data/kube_pod_container_resource_requests.csv" "$CURRENT_PATH/data/karpenter_pods_state.csv"

# Remember to enable prometheus and grafana ports
python3 trace_execution.py