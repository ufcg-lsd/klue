#!/bin/bash

# Função para exibir a ajuda
usage() {
    echo "Uso: $0 [--dev | --sim] [--use-cluster CONTEXT] [--data-path PATH] [--nodepool-path PATH] [--use-karpenter] [--skip-tracer] [--static-infra] [--static-workload] [-h | --help]"
    echo ""
    echo "Opções:"
    echo "  --dev                 Criar ambiente de desenvolvimento"
    echo "  --sim                 Criar ambiente de emulação"
    echo "  --use-cluster CONTEXT Usar um cluster existente (passe o nome do contexto)"
    echo "  --data-path PATH      Especificar o caminho do trace a ser usado na emulação"
    echo "  --nodepool-path PATH  Especificar o caminho do nodepool a ser usado na emulação"
    echo "  --use-karpenter       Ativar o Karpenter para gerenciamento de nós"
    echo "  --skip-tracer         Pular a execução do tracer"
    echo "  --static-infra        Usar infraestrutura estática na emulação"
    echo "  --static-workload     Usar workload estático na emulação"
    echo "  -h, --help            Exibir esta mensagem de ajuda"
    exit 1
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
NODEPOOL_PATH=""
TRACER="no-skip"
KARPENTER="karpenter-off"
INFRASTRUCTURE="dynamic"
WORKLOAD="dynamic"

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
        --data-path)
            TRACE_PATH="$2"
            shift 2
            ;;
        --nodepool-path)
            NODEPOOL_PATH="$2"
            shift 2
            ;;
        --use-karpenter)
            KARPENTER="karpenter-on"
            shift
            ;;
        --skip-tracer)
            TRACER="skip-tracer"
            shift
            ;;
        --static-infra)
            INFRASTRUCTURE="static"
            shift
            ;;
        --static-workload)
            WORKLOAD="static"
            shift
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
    echo "Erro: É necessário especificar --data-path ao usar --sim."
    usage
fi

if [[ $ENVIRONMENT == "emulation" && $KARPENTER == "karpenter-on" && -z $NODEPOOL_PATH ]]; then
    echo "Erro: É necessário especificar --nodepool-path ao usar --sim com --use-karpenter."
    usage
fi

# Configuração do ambiente
if [[ $ENVIRONMENT == "development" ]]; then
    echo "Configurando ambiente de desenvolvimento..."
    cd kwok-karpenter-install
    ./setup.sh "$KARPENTER"
elif [[ $ENVIRONMENT == "emulation" ]]; then
    echo "Configurando ambiente de emulação..."
    cd kwok-karpenter-install
    ./setup.sh "$KARPENTER"
    cd ..
    python3 src/main.py "$TRACE_PATH" "$NODEPOOL_PATH" "$KARPENTER" "$TRACER" "$INFRASTRUCTURE" "$WORKLOAD"
fi
