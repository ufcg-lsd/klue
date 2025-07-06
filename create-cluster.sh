#!/bin/bash
# Load env variables
set -a
source .env
set +a

set -e

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "Which type of cluster do you want to create?"
echo "1) EKS Environment"
echo "2) Minikube Environment"
echo "3) Kind Environment"
read CLUSTER_CHOICE

if [ "$CLUSTER_CHOICE" == "1" ]; then
    # EKS (AWS)
    if ! command_exists aws; then
        echo "AWS CLI not found. Please install it and try again."
        exit 1
    fi

    if ! aws configure list-profiles | grep -q "^$AWS_PROFILE$"; then
        echo "Default AWS CLI profile not found. Please configure it and try again."
        exit 1
    fi

    if ! command_exists eksctl; then
        echo "eksctl not found. Please install it and try again."
        exit 1
    fi

    if ! command_exists kubectl; then
        echo "kubectl not found. Please install it and try again."
        exit 1
    fi

    if ! command_exists helm; then
        echo "helm not found. Please install it and try again."
        exit 1
    fi

    USERNAME=$(aws sts get-caller-identity --query 'Arn' --output text | awk -F'/' '{print $NF}' | sed -E 's/[_@].*//')
    export USERNAME

    echo "Creating EKS cluster: $CLUSTER_NAME in region: $REGION"
    envsubst < $CLUSTER_CONFIG_FILE | eksctl create cluster -f -

    echo "Updating kubeconfig for the cluster..."
    aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION --profile $AWS_PROFILE

    echo "Verifying the cluster status..."
    kubectl get svc

    echo "Creating the first cluster nodegroup for user $USERNAME..."
    envsubst < $NODEGROUP_CONFIG_FILE | eksctl create nodegroup -f - || true

    QUEUE_URL=$(aws sqs list-queues --region "$REGION" --profile "$AWS_PROFILE" | grep "$QUEUE_NAME") || true

    if [ -n "$QUEUE_URL" ]; then
        echo "Queue '$QUEUE_NAME' already exists. URL: $QUEUE_URL"
    else
        echo "Queue '$QUEUE_NAME' does not exist. Creating it now..."
        QUEUE_URL=$(aws sqs create-queue --queue-name "$QUEUE_NAME" --region "$REGION" --profile "$AWS_PROFILE" --query 'QueueUrl' --output text)
        if [ $? -eq 0 ]; then
            echo "Queue '$QUEUE_NAME' created successfully. URL: $QUEUE_URL"
        else
            echo "Failed to create queue '$QUEUE_NAME'."
            exit 1
        fi
    fi

elif [ "$CLUSTER_CHOICE" == "2" ]; then
    echo "Minikube selected. (Add your code here to create the Minikube cluster)"
    minikube start --cpus='4' --memory='6g'
elif [ "$CLUSTER_CHOICE" == "3" ]; then
    echo "Kind selected."
    kind create cluster --name klue-cluster
    kind get kubeconfig --name klue-cluster > kwok.kubeconfig

    CONTROL_PLANE_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' klue-cluster-control-plane)
    sed -i "s|server: https://127.0.0.1:[0-9]*|server: https://$CONTROL_PLANE_IP:6443|g" kwok.kubeconfig

    kubectl create configmap kwok-kubeconfig --from-file=kwok.kubeconfig=kwok.kubeconfig -n default
    rm kwok.kubeconfig
else
    echo "Invalid option. Exiting."
    exit 1
fi