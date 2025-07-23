#!/bin/bash

source .env

set -e

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if [ -n "$1" ]; then
    CLUSTER_CHOICE="$1"
else
    echo "Which type of cluster do you want to delete?"
    echo "1) EKS Environment"
    echo "2) Minikube Environment"
    echo "3) Kind Environment"
    read -p "Enter the number of your choice 1, 2 or 3: " CLUSTER_CHOICE
fi

if [ "$CLUSTER_CHOICE" == "1" ]; then
    # EKS (AWS) deletion
    if ! command_exists aws; then
        echo "AWS CLI not found. Please install it and try again."
        exit 1
    fi

    if ! command_exists eksctl; then
        echo "eksctl not found. Please install it and try again."
        exit 1
    fi

    remove_tags() {
        RESOURCE_IDS="$1"
        TAGS="$2"
        echo "Removing tags from resources: $RESOURCE_IDS"
        aws ec2 delete-tags --resources $RESOURCE_IDS --tags $TAGS --region $REGION
    }

    echo "Retrieving Security Group associated with the cluster..."
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=tag:aws:eks:cluster-name,Values=$CLUSTER_NAME" --query "SecurityGroups[*].GroupId" --output text) || true

    if [ -n "$SECURITY_GROUP_ID" ]; then
        echo "Removing tags from Security Group $SECURITY_GROUP_ID"
        remove_tags "$SECURITY_GROUP_ID" "Key=karpenter.sh/discover,Value=$CLUSTER_NAME"
    else
        echo "No Security Group found for cluster $CLUSTER_NAME."
    fi

    echo "Retrieving Subnets associated with the cluster..."
    SUBNET_IDS=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.resourcesVpcConfig.subnetIds" --output text)  || true

    if [ -n "$SUBNET_IDS" ]; then
        echo "Removing tags from Subnets $SUBNET_IDS"
        remove_tags "$SUBNET_IDS" "Key=karpenter.sh/discovery,Value=$CLUSTER_NAME"
    else
        echo "No Subnets found for cluster $CLUSTER_NAME."
    fi

    echo "Deleting SQS queue named $QUEUE_NAME..."
    QUEUE_URL=$(aws sqs list-queues --queue-name-prefix "$QUEUE_NAME" --region "$REGION" --output text | grep "$QUEUE_NAME") || true

    if [ -n "$QUEUE_URL" ]; then
        aws sqs delete-queue --queue-url "$QUEUE_NAME" --region "$REGION" || true
        echo "Queue $QUEUE_NAME deleted successfully."
    else
        echo "Queue $QUEUE_NAME not found or already deleted."
    fi

    echo "Uninstalling Karpenter..."
    helm uninstall karpenter --namespace $KARPENTER_NAMESPACE --timeout=60s || true
    kubectl delete namespace $KARPENTER_NAMESPACE --timeout=60s || true

    echo "Deleting EKS cluster: $CLUSTER_NAME in region: $REGION"
    eksctl delete cluster --name $CLUSTER_NAME --region $REGION --disable-nodegroup-eviction || echo "Failed to delete cluster using eksctl, trying CloudFormation deletion."

    STACK_NAME="eksctl-${CLUSTER_NAME}-cluster"
    echo "Deleting CloudFormation stack: $STACK_NAME"
    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

    echo "Waiting for CloudFormation stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION

    echo "Confirming cluster deletion..."
    CLUSTER_STATUS=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query 'cluster.status' --output text 2>/dev/null || echo "DELETED")

    if [ "$CLUSTER_STATUS" == "DELETED" ]; then
        echo "Cluster $CLUSTER_NAME has been successfully deleted."
    else
        echo "Cluster $CLUSTER_NAME deletion is still in progress or failed. Current status: $CLUSTER_STATUS"
    fi

elif [ "$CLUSTER_CHOICE" == "2" ]; then
    echo "Minikube selected. Deleting Minikube cluster..."
    minikube delete -p minikube || echo "Failed to delete Minikube cluster. It may not exist or is already deleted."
elif [ "$CLUSTER_CHOICE" == "3" ]; then
    echo "Kind selected. Deleting Kind cluster..."
    kind delete cluster --name klue-cluster || echo "Failed to delete Kind cluster."
else
    echo "Invalid option. Exiting."
    exit 1
fi