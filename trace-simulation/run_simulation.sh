#!/bin/bash

CURRENT_PATH=$(pwd)

kubectl apply -f "$CURRENT_PATH/data/nodepools.yaml"

python3 trace_setup.py "$CURRENT_PATH/data/kube_pod_container_resource_requests.csv" "$CURRENT_PATH/data/karpenter_pods_state.csv" "$CURRENT_PATH/data/kube_pod_owner.csv" "$CURRENT_PATH/data/kube_replicaset_owner.csv"

python3 trace_execution.py
