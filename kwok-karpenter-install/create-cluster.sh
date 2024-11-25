#!/bin/bash
# Load env variables
set -a
source ../.env
set +a

# Exit immediately if a command exits with a non-zero status
set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for AWS CLI
if ! command_exists aws; then
    echo "AWS CLI not found. Please install it and try again."
    exit 1
fi

# Check if the default profile exists
if ! aws configure list-profiles | grep -q "^$AWS_PROFILE$"; then
    echo "Default AWS CLI profile not found. Please configure it and try again."
    exit 1
fi

# Check for eksctl
if ! command_exists eksctl; then
    echo "eksctl not found. Please install it and try again."
    exit 1
fi

# Check for kubectl
if ! command_exists kubectl; then
    echo "kubectl not found. Please install it and try again."
    exit 1
fi

# Check for helm
if ! command_exists helm; then
    echo "helm not found. Please install it and try again."
    exit 1
fi

# Get and export the USERNAME of the user executing this script
USERNAME=$(aws sts get-caller-identity --query 'Arn' --output text | awk -F'/' '{print $NF}' | sed -E 's/[_@].*//')
export USERNAME

# Create the EKS cluster from the file cluster-config.yaml
echo "Creating EKS cluster: $CLUSTER_NAME in region: $REGION"
envsubst < $CLUSTER_CONFIG_FILE | eksctl create cluster -f -

# Update kubeconfig
echo "Updating kubeconfig for the cluster..."
aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION --profile $AWS_PROFILE

# Verify cluster is up and running
echo "Verifying the cluster status..."
kubectl get svc

# Create the first cluster node to run karpenter
echo "Creating the first cluster nodegroup for user $USERNAME..."
envsubst < $NODEGROUP_CONFIG_FILE | eksctl create nodegroup -f - || true

# List all queues and search for the specific queue by name
QUEUE_URL=$(aws sqs list-queues --region "$REGION" --profile "$AWS_PROFILE" | grep "$QUEUE_NAME") || true

# Check if QUEUE_URL is empty or not
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
