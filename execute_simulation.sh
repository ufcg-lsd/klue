#!/bin/bash

echo "Você deseja criar um ambiente de desenvolvimento ou um ambiente de simulação?"
echo "1) Ambiente de Desenvolvimento"
echo "2) Ambiente de Simulação"
read -p "Digite o número correspondente à sua escolha (1 ou 2): " escolha

choose_cluster() {
    echo "Verificando contextos de clusters disponíveis..."
    CONTEXTS=$(kubectl config get-contexts -o name 2>/dev/null)

    if [[ -z $CONTEXTS ]]; then
        echo "Nenhum contexto encontrado. Criando um novo cluster..."
        echo "Criando cluster..."
        cd kwok-karpenter-install
        ./create-cluster.sh
        cd ..
    else
        echo "Contextos disponíveis:"
        select context in $CONTEXTS "Criar novo cluster"; do
            if [[ -z $context ]]; then
                echo "Opção inválida. Por favor, selecione novamente."
            elif [[ $context == "Criar novo cluster" ]]; then
                echo "Criando cluster..."
                cd kwok-karpenter-install
                ./create-cluster.sh
                cd ..
                break
            else
                echo "Usando o cluster existente: $context"
                kubectl config use-context $context
                break
            fi
        done
    fi
}

if [[ $escolha -eq 1 ]]; then
    echo "Criando ambiente de desenvolvimento..."
    cd kwok-karpenter-install
    ./create-cluster.sh
    ./setup.sh
elif [[ $escolha -eq 2 ]]; then
    echo "Criando ambiente de simulação..."
    choose_cluster
    cd kwok-karpenter-install
    ./setup.sh
    cd ../trace-simulation
    ./run_simulation.sh
else
    echo "Opção inválida. Por favor, execute novamente e escolha 1 ou 2."
    exit 1
fi

