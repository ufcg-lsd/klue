# Creating or setting up an EKS Cluster
There are two main ways to run the emulation tool on EKS: using an existing cluster or creating a new one. This guide will help you set up your environment and run the emulation tool effectively.
---

## 🛠 Installation Guide
Before testing your solutions and configurations, follow these steps to properly set up your environment.

### 📌 Install Dependencies
To create your emulated cluster, you first need **access to AWS** and must install the required dependencies:

1. **MINIKUBE** – Follow this [installation guide](https://minikube.sigs.k8s.io/docs/start/)
2. **KUBECTL** – Install via this [tutorial](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
3. **HELM** – Kubernetes package manager, install via [this guide](https://helm.sh/docs/intro/install/)
4. **Python3 Libraries** – Install the necessary libraries as listed in the requirements.txt

---

## 📌 Creating a Minikube cluster
### Requirements
- **CPU**: **More than** 4 CPUs free in your system
- **Memory**: **More than** 8 GB of RAM free in your system

### Starting Minikube
To create a Minikube cluster, you can use the following command:
```bash
minikube start --cpus='4' --memory='8g'
```

# Running the Emulation Tool

For minikube, the only avaible option is to create a new cluster before start the emulation, so you just need to pass the flag **--use-cluster** to the script, like this:
```bash
./execute_emulation.sh --use-cluster minikube <other arguments>
```

To know more about the arguments, please visit the session **Executing the Emulation Tool** on our [README.md](https://github.com/ufcg-lsd/klue/tree/main/#readme).