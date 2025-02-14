# 🚀 KLUE – A VTEX Lab Tool for Emulating Infrastructure and Workload  

KLUE is a **emulation tool** that allows developers to **test and validate cloud infrastructure changes** without incurring unnecessary expenses. It enables seamless **Kubernetes** experimentation, helping teams optimize configurations, improve scalability, and reduce cloud costs.

---

## 🛠 Installation Guide  
Before testing your solutions and configurations, follow these steps to properly set up your environment.  

### 📌 Install Dependencies  
To create your emulated cluster, you first need **access to AWS** and must install the required dependencies:

1. **EKSCTL** – Follow this [installation guide](https://eksctl.io/installation/)  
2. **KUBECTL** – Install via this [tutorial](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)  
3. **AWS CLI** – Install using [this guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)  
4. **HELM** – Kubernetes package manager, install via [this guide](https://helm.sh/docs/intro/install/)  
5. **AWS SSO Configuration** – Follow [this tutorial](https://pushkar-sre.medium.com/how-to-set-up-aws-cli-with-aws-single-sign-on-sso-acf4dd88e056) to configure your default profile  

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
```
cp .env.example .env
```

After this, init the submodule repositories `prometheus` and `karpenter-code` using
```
git submodule update --init --recursive
```
---
## 🚀 Executing the Emulation Tool  

### 📂 Ensure Your Entry Files Are in the `data` Directory  
Please visit the `README.md` in `trace-emulator/data` to understand how your files should be structured.  

### 🔑 Grant Execution Permission  
Before running an emulation, grant execution permission to the **execute_emulation.sh** file by running:

```
chmod +x execute_emulation.sh
```
### ▶️ Run the Execution Manager  
There are multiple ways to run our emulation tool. One method is by using an **existing cluster** with at least **one node**:

```
./execute_emulation.sh --sim --use-cluster <cluster-context> --trace-path <trace-path>
```
You can also create a **new cluster** with **one node**. To do that, you must have the roles set in your .env file:

```
./execute_emulation.sh --sim --new-cluster --trace-path <trace-path>
```
If you don't have sure about the flags, please use the following command:
```
./execute_emulation.sh --help
```
---
## Exemplo de execução da ferramenta
![Demo do KLUE](assets/emulation-running.gif)
---

## 👥 Developed by VTEX Lab Members  
- **Kayky Fidelis – Undergraduate Student, Federal University of Campina Grande (UFCG)** – [LinkedIn](https://www.linkedin.com/in/kayky-fidelis/)  
- **Geraldo Sobreira – Undergraduate Student, Federal University of Campina Grande (UFCG)** – [LinkedIn](https://www.linkedin.com/in/geraldo-sobreira-junior/)  
- **Eric Matozo – Master's Student, Federal University of Campina Grande (UFCG)** – [LinkedIn](https://www.linkedin.com/in/ericmatozo/)  

## 👨‍🏫 Supervised by  
- **Giovanni Farias – PhD, Federal University of Campina Grande (UFCG)**  
- **Fábio Morais – PhD, Federal University of Campina Grande (UFCG)**  
