#!/bin/bash

# Verifica se o caminho do trace foi fornecido
if [ $# -lt 1 ]; then
  echo "Uso: $0 <trace_path>"
  exit 1
fi

TRACE_PATH=$1

CURRENT_PATH=$(pwd)

# Aplica os recursos do nodepool
kubectl apply -f "$CURRENT_PATH/data/nodepools.yaml"

python3 trace_setup.py "$CURRENT_PATH/data/kube_pod_container_resource_requests_8_hours.csv" "$CURRENT_PATH/data/karpenter_pods_state_8_hours.csv" "$CURRENT_PATH/data/kube_pod_owner_8_hours.csv" "$CURRENT_PATH/data/kube_replicaset_owner_8_hours.csv"

# Executa o trace_execution.py
python3 trace_execution.py

