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

python3 tracer.py "$TRACE_PATH/kube_pod_container_resource_requests.csv" "$TRACE_PATH/karpenter_pods_state.csv" "$TRACE_PATH/kube_pod_owner.csv" "$TRACE_PATH/kube_replicaset_owner.csv"

# Executa o broker.py
python3 broker.py

