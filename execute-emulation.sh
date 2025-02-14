#!/bin/bash

# Função para exibir a ajuda
usage() {
    echo "Uso: $0 [--dev | --sim] [--use-cluster CONTEXT | --new-cluster] [--trace-path PATH]"
    echo ""
    echo "Opções:"
    echo "  --dev                 Criar ambiente de desenvolvimento"
    echo "  --sim                 Criar ambiente de emulação"
    echo "  --use-cluster CONTEXT Usar um cluster existente (passe o nome do contexto)"
    echo "  --new-cluster         Criar um novo cluster"
    echo "  --trace-path PATH     Especificar o caminho do trace a ser usado na emulação"
    echo "  -h, --help            Exibir esta mensagem de ajuda"
    exit 1
}

# Função para criar um cluster novo
create_new_cluster() {
    echo "Criando cluster novo..."
    cd kwok-karpenter-install
    ./create-cluster.sh
    cd ..
}

# Função para configurar um cluster existente
use_existing_cluster() {
    local context=$1
    echo "Usando o cluster existente: $context"
    kubectl config use-context "$context"
}

# Parsing das flags
ENVIRONMENT=""
CLUSTER_ACTION=""
CLUSTER_CONTEXT=""
TRACE_PATH=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            ENVIRONMENT="development"
            shift
            ;;
        --sim)
            ENVIRONMENT="emulation"
            shift
            ;;
        --use-cluster)
            CLUSTER_ACTION="use"
            CLUSTER_CONTEXT="$2"
            shift 2
            ;;
        --new-cluster)
            CLUSTER_ACTION="new"
            shift
            ;;
        --trace-path)
            TRACE_PATH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Opção inválida: $1"
            usage
            ;;
    esac
done

# Validação das flags
if [[ -z $ENVIRONMENT ]]; then
    echo "Erro: É necessário especificar --dev ou --sim."
    usage
fi

if [[ $CLUSTER_ACTION == "use" && -z $CLUSTER_CONTEXT ]]; then
    echo "Erro: O nome do contexto é necessário ao usar --use-cluster."
    usage
fi

if [[ $ENVIRONMENT == "emulation" && -z $TRACE_PATH ]]; then
    echo "Erro: É necessário especificar --trace-path ao usar --sim."
    usage
fi

# Execução das ações
if [[ $CLUSTER_ACTION == "new" ]]; then
    create_new_cluster
elif [[ $CLUSTER_ACTION == "use" ]]; then
    use_existing_cluster "$CLUSTER_CONTEXT"
else
    echo "Nenhuma ação de cluster especificada. Criando um novo cluster por padrão."
    create_new_cluster
fi

# Configuração do ambiente
if [[ $ENVIRONMENT == "development" ]]; then
    echo "Configurando ambiente de desenvolvimento..."
    cd kwok-karpenter-install
    ./setup.sh
elif [[ $ENVIRONMENT == "emulation" ]]; then
    echo "Configurando ambiente de emulação..."
    cd kwok-karpenter-install
    ./setup.sh
    cd ../trace-emulation
    ./run-emulation.sh "$TRACE_PATH"
fi

