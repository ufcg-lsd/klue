#!/bin/bash

# Script to install dependencies for Kubernetes development environments (EKS or Minikube).
# Usage: ./install_dependencies.sh

# Exit if any command fails
set -e

# --- Installation Functions ---

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Install Docker
install_docker() {
    if command_exists docker; then
        echo "Docker is already installed."
        return
    fi
    echo "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo groupadd docker
    # Add current user to docker group to run without sudo
    sudo usermod -aG docker "${USER}"
    newgrp docker
    echo "Docker installed successfully. Please logout and login again to use Docker without 'sudo'."
}

# 2. Install kubectl
install_kubectl() {
    if command_exists kubectl; then
        echo "kubectl is already installed."
        return
    fi
    echo "Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
    echo "kubectl installed successfully."
}

# 3. Install Helm
install_helm() {
    if command_exists helm; then
        echo "Helm is already installed."
        return
    fi
    echo "Installing Helm..."
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 get_helm.sh
    ./get_helm.sh
    rm get_helm.sh
    echo "Helm installed successfully."
}

# 4. Install AWS CLI
install_aws_cli() {
    if command_exists aws; then
        echo "AWS CLI is already installed."
        return
    fi
    echo "Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf aws awscliv2.zip
    echo "AWS CLI installed successfully."
}

# 5. Install eksctl
install_eksctl() {
    if command_exists eksctl; then
        echo "eksctl is already installed."
        return
    fi
    echo "Installing eksctl..."
    # For amd64 architecture. Change to arm64 if needed.
    ARCH="amd64"
    PLATFORM="$(uname -s)_$ARCH"
    curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$PLATFORM.tar.gz" | tar xz -C /tmp
    sudo mv /tmp/eksctl /usr/local/bin
    echo "eksctl installed successfully."
}

# 6. Install Minikube
install_minikube() {
    if command_exists minikube; then
        echo "Minikube is already installed."
        return
    fi
    echo "Installing Minikube..."
    curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64
    echo "Minikube installed successfully."
}

# 7. Install Python libraries
install_python_deps() {
    sudo apt install python3.10-venv 

    # Check if a virtual environment is already activated
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "A Python virtual environment is already activated: $VIRTUAL_ENV"
    else
        # Check if venv directory exists
        if [ -d "venv" ]; then
            echo "Using existing Python virtual environment in ./venv"
        else
            echo "Creating new Python virtual environment in ./venv"
            python3 -m venv venv
        fi
        source venv/bin/activate
    fi

    if [ ! -f "requirements.txt" ]; then
        echo "Warning: 'requirements.txt' file not found. Skipping Python dependencies installation."
        return
    fi
    echo "Installing Python libraries from requirements.txt..."
    pip install -r requirements.txt
    echo "Python libraries installed successfully."
}

# 8 Install auxiliary dependencies
install_aux_deps() {
    echo "Installing auxiliary dependencies..."
    sudo apt-get update
    sudo apt-get install -y \
        jq
}


# --- Main Script Logic ---

YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "This script will install dependencies for the development environment."
echo "Please choose the environment you want to set up:"
echo "1) EKS Environment (includes eksctl, aws-cli)"
echo "2) Minikube Environment (includes minikube)"
read -p "Enter 1 or 2: " choice

case $choice in
    1)
        echo "--- Setting up EKS Environment ---"
        git submodule update --init --recursive
        install_aux_deps
        install_docker
        install_kubectl
        install_helm
        install_aws_cli
        install_eksctl
        install_python_deps
        echo ""
        echo -e "${YELLOW}--- MANUAL ACTION REQUIRED ---${NC}"
        echo -e "${YELLOW}To configure access via AWS SSO, follow the tutorial:${NC}"
        echo "https://pushkar-sre.medium.com/how-to-set-up-aws-cli-with-aws-single-sign-on-sso-acf4dd88e056"
        echo "After configuring, you may need to login with 'aws sso login'."
        echo "--------------------------------"
        echo -e "${YELLOW}To ACTIVATE the Python virtual environment, run:${NC}"
        echo "source venv/bin/activate"
        echo -e "${YELLOW}Enter in your docker account by running:${NC}"
        echo "docker login"
        echo "--------------------------------"
        ;;
    2)
        echo "--- Setting up Minikube Environment ---"
        git submodule update --init --recursive
        install_aux_deps
        install_docker
        install_kubectl
        install_helm
        install_minikube
        install_python_deps
        echo ""
        echo -e "${YELLOW}--- MANUAL ACTION REQUIRED ---${NC}"
        echo "--------------------------------"
        echo -e "${YELLOW}ACTIVATE the Python virtual environment, running:${NC}"
        echo "source venv/bin/activate"
        echo -e "${YELLOW}Enter in your docker account by running:${NC}"
        echo "docker login"
        echo "--------------------------------"
        ;;
    *)
        echo "Invalid option. Exiting."
        exit 1
        ;;
esac

echo "Installation completed!"
