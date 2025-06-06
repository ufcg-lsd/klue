# Creating or setting up an EKS Cluster
There are two main ways to run the emulation tool on EKS: using an existing cluster or creating a new one. This guide will help you set up your environment and run the emulation tool effectively.
---

## 🛠 Installation Guide
Follow these steps to properly set up your environment.

### 📌 Install Dependencies
To create your emulated cluster, you first need **access to AWS** and must install the required dependencies:

1. **EKSCTL** – Follow this [installation guide](https://eksctl.io/installation/)
2. **KUBECTL** – Install via this [tutorial](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
3. **AWS CLI** – Install using [this guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
4. **HELM** – Kubernetes package manager, install via [this guide](https://helm.sh/docs/intro/install/)
5. **DOCKER** – Install Docker by following [this guide](https://docs.docker.com/engine/install/ubuntu/)
6. **AWS SSO Configuration** – Follow [this tutorial](https://pushkar-sre.medium.com/how-to-set-up-aws-cli-with-aws-single-sign-on-sso-acf4dd88e056) to configure your default profile
7. **Python3 Libraries** – Install the necessary libraries as listed in the requirements.txt

---

### 📌 Environment Variables

| **Variable**              | **Description** |
|---------------------------|---------------|
| `CLUSTER_NAME`           | Name of your cluster |
| `EKS_VERSION`            | EKS version to install |
| `CLUSTER_CREATION_ARN`   | ARN with permissions to create the cluster |
| `INSTANCE_ROLE_ARN`      | ARN with permissions to launch and manage instances |
| `INSTANCE_PROFILE_ARN`   | Profile ARN with instance management permissions |
| `SERVICE_ROLE_ARN`       | Service ARN with instance management permissions |
| `REGION`                 | AWS Region |
| `ENVIRONMENT`            | Environment tag for ASG |
| `PRODUCT`               | Product tag |
| `APPLICATION_NAME`       | Required tag to create the ASG |
| `AWS_PROFILE`           | AWS SSO profile name |
| `CLUSTER_CONFIG_FILE`    | Path of the cluster configuration file |
| `NODEGROUP_CONFIG_FILE`  | Path of the nodegroup configuration file |
| `NODECLASS_CONFIG_FILE`  | Path of the nodeclass configuration file |
| `NODEPOOL_CONFIG_FILE`   | Path of the nodepool configuration file |
| `CALICO_CONFIG_FILE`     | Path of the Calico configuration file |
| `CLUSTER_CNI`           | Set to `AmazonVPC` (VPC CNI) or `Calico` (Calico CNI) |
| `QUEUE_NAME`            | Name of the queue (if not using an existing one) |
| `KARPENTER_VERSION`     | Karpenter Version |
| `KARPENTER_NAMESPACE`   | Namespace to install Karpenter |
| `CALICO_NAMESPACE`      | Namespace to install Calico |

Once you have these dependencies installed, copy the `env.example` file to your `.env` using:
```bash
cp .env.example .env
```

# Running the Emulation Tool

If you want to create a new cluster, you just need to pass the flag **--new-cluster** to the script, like this:
```bash
./execute_emulation.sh --new-cluster <other arguments>
```

If you want to use an existing cluster, you need to pass the flag **--use-cluster** to the script, like this:
```bash
./execute_emulation.sh --use-cluster <cluster-context> <other arguments>
```

To know more about the arguments, please visit the session **Executing the Emulation Tool** on our [README.md](https://github.com/ufcg-lsd/klue/tree/main/#readme).