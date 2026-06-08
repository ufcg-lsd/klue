#!/bin/bash
set -e

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

OS="$(uname -s)"

echo "🔧 Installing KLUE development dependencies"
echo "Detected OS: $OS"

# =========================
# macOS
# =========================
install_macos_deps() {
  echo "🍎 Setting up macOS development environment"

  # 1️⃣ Homebrew
  if ! command_exists brew; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  brew update

  # 2️⃣ Docker Desktop
  if ! command_exists docker; then
    echo "Installing Docker Desktop..."
    brew install --cask docker
    echo "⚠️ Please open Docker.app and finish setup before continuing"
  fi

  # 3️⃣ kubectl
  brew install kubectl || true

  # 4️⃣ Helm
  brew install helm || true

  # 5️⃣ AWS CLI
  brew install awscli || true

  # 6️⃣ eksctl
  brew install eksctl || true

  # 7️⃣ Minikube
  brew install minikube || true

  # 8️⃣ Go (required by KLUE / Kubernetes tooling)
  brew install go || true

  # 9️⃣ Python
  brew install python@3.11 || true

  # 🔟 Python venv
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi

  source venv/bin/activate

  if [ -f requirements.txt ]; then
    pip install -r requirements.txt
  fi

  echo "✅ macOS environment ready"
  echo "👉 Activate venv: source venv/bin/activate"
}

# =========================
# Linux (Ubuntu/Debian)
# =========================
install_linux_deps() {
  echo "🐧 Setting up Linux development environment"

  sudo apt-get update

  # Base tools
  sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    jq \
    unzip

  # Docker (host only)
  if ! command_exists docker; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "⚠️ Logout/login required for Docker group changes"
  fi

  # kubectl
  if ! command_exists kubectl; then
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
  fi

  # Helm
  if ! command_exists helm; then
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  fi

  # Minikube
  if ! command_exists minikube; then
    curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64
  fi

  # Go
  if ! command_exists go; then
    GO_VERSION="1.22.1"
    curl -LO https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz
    rm go${GO_VERSION}.linux-amd64.tar.gz
    echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
  fi

  # Python
  sudo apt-get install -y python3 python3-venv python3-pip

  # Python venv
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi

  source venv/bin/activate

  if [ -f requirements.txt ]; then
    pip install -r requirements.txt
  fi

  echo "✅ Linux environment ready"
  echo "👉 Activate venv: source venv/bin/activate"
}

# =========================
# OS Dispatch
# =========================
case "$OS" in
  Darwin)
    install_macos_deps
    ;;
  Linux)
    install_linux_deps
    ;;
  *)
    echo "❌ Unsupported OS: $OS"
    exit 1
    ;;
esac
