#!/bin/bash

# Verifica se o caminho do trace foi fornecido
if [ $# -lt 1 ]; then
  echo "Uso: $0 <trace_path>"
  exit 1
fi

TRACE_PATH=$1

# Verifica se o arquivo especificado existe
if [ ! -f "$TRACE_PATH" ]; then
  echo "Erro: Arquivo $TRACE_PATH não encontrado."
  exit 1
fi

CURRENT_PATH=$(pwd)

# Aplica os recursos do nodepool
kubectl apply -f "$CURRENT_PATH/data/nodepools.yaml"

# Passa o trace path como argumento para o script trace_setup.py
python3 trace_setup.py "$TRACE_PATH"

# Executa o trace_execution.py
python3 trace_execution.py

