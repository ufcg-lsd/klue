#!/bin/bash

echo "Você deseja criar um ambiente de desenvolvimento ou um ambiente de simulação?"
echo "1) Ambiente de Desenvolvimento"
echo "2) Ambiente de Simulação"
read -p "Digite o número correspondente à sua escolha (1 ou 2): " escolha

if [[ $escolha -eq 1 ]]; then
    echo "Criando ambiente de desenvolvimento..."
    cd kwok-karpenter-install
    ./create-cluster.sh
    ./setup.sh
elif [[ $escolha -eq 2 ]]; then
    echo "Criando ambiente de simulação..."
    cd kwok-karpenter-install
    ./create-cluster.sh
    ./setup.sh
    cd ../trace-simulation
    ./run_simulation.sh
else
    echo "Opção inválida. Por favor, execute novamente e escolha 1 ou 2."
    exit 1
fi

