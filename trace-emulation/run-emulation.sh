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

python3 tracer.py "$CURRENT_PATH/data/kube_pod_container_resource_requests.csv" "$CURRENT_PATH/data/karpenter_pods_state.csv" "$CURRENT_PATH/data/kube_pod_owner.csv" "$CURRENT_PATH/data/kube_replicaset_owner.csv"

# Executa o broker.py
python3 broker.py

