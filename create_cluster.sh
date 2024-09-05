#!/bin/bash

# Load env variables
set -a
source .env
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

# Create the EKS cluster from the file cluster-config.yaml
echo "Creating EKS cluster: $CLUSTER_NAME in region: $REGION"
envsubst < $CLUSTER_CONFIG_FILE | eksctl create cluster -f -

# Update kubeconfig
echo "Updating kubeconfig for the cluster..."
aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION --profile $AWS_PROFILE

# Verify cluster is up and running
echo "Verifying the cluster status..."
kubectl get svc

# Delete the existing aws-node DaemonSet, which is replaced by Calico
echo "Deleting the aws-node daemonset"
kubectl delete daemonset -n kube-system aws-node

# Install Calico CRDs
echo "Installing Calico CRD's"
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.1/manifests/tigera-operator.yaml

# Install Calico and apply the installation yaml
echo "Applying calico instalation into the cluster"
envsubst < $CALICO_CONFIG_FILE | eksctl create -f -

# Create the first cluster node to run karpenter
echo "Creating the first cluster nodegroup..."
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

# Install Karpenter using Helm and configure it to work with the cluster
helm upgrade --install karpenter oci://public.ecr.aws/karpenter/karpenter \
    --version "0.37.0" \
    --namespace "karpenter" \
    --create-namespace \
    --set "settings.clusterName=$CLUSTER_NAME" \
    --set "settings.interruptionQueue=$QUEUE_NAME" \
    --set controller.resources.requests.cpu=1 \
    --set controller.resources.requests.memory=1Gi \
    --set controller.resources.limits.cpu=1 \
    --set controller.resources.limits.memory=1Gi \
    --set replicas=1 \
    --wait

# Verify Karpenter installation
echo "Verifying Karpenter installation..."
kubectl get pods -n $KARPENTER_NAMESPACE || true
echo "Karpenter installation completed successfully!"

# Tag the Security Group associated with the EKS cluster
echo "Tagging security group"
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=tag:aws:eks:cluster-name,Values=$CLUSTER_NAME" --query "SecurityGroups[0].GroupId" --output text) || true
aws ec2 create-tags --resources "$SECURITY_GROUP_ID" --tags Key=karpenter.sh/discovery,Value=$CLUSTER_NAME

# Tag the subnets associated with the EKS cluster
echo "Tagging subnets"
SUBNET_IDS=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.resourcesVpcConfig.subnetIds" --output text) || true

for SUBNET_ID in $SUBNET_IDS; do
    echo "Tagging subnet $SUBNET_ID with karpenter.sg=$CLUSTER_NAME"
    aws ec2 create-tags --resources $SUBNET_ID --tags Key=karpenter.sh/discovery,Value=$CLUSTER_NAME
done

# Apply the NodeClass and NodePool configurations for Karpenter
echo "Applying nodeclass"
envsubst < $NODECLASS_CONFIG_FILE | kubectl apply -f - || true

echo "Applying nodepool"
envsubst < $NODEPOOL_CONFIG_FILE | kubectl apply -f - || true

# List the EC2 NodeClasses and NodePools to verify their creation
kubectl get ec2nodeclass
kubectl get nodepool
