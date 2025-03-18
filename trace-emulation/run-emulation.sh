#!/bin/bash

if [ $# -lt 2 ]; then
  echo "Uso: $0 <trace_path> <nodepool_path>"
  exit 1
fi

TRACE_PATH=$1
NODEPOOL_PATH=$2

kubectl apply -f "$NODEPOOL_PATH"

python3 tracer.py "$TRACE_PATH/kube_pod_container_resource_requests_reduced.csv" \
                  "$TRACE_PATH/karpenter_pods_state_reduced.csv" \
                  "$TRACE_PATH/kube_pod_owner_reduced.csv" \
                  "$TRACE_PATH/kube_replicaset_owner_reduced.csv"

# Executa o broker.py
python3 broker.py
