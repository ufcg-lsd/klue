# 🚀 KLUE – A VTEX Lab Tool for Emulating Infrastructure and Workload

KLUE is a **emulation tool** that allows developers to **test and validate cloud infrastructure changes** without incurring unnecessary expenses. It enables seamless **Kubernetes** experimentation, helping teams optimize configurations, improve scalability, and reduce cloud costs.

---

## 🛠 Installation Guide
Execute our emulation tool is a very simple process, but it requires a configured cluster (or the informations to create it automatically). Before start, consideer read [this guide](https://github.com/ufcg-lsd/klue/tree/main/docs/#minikube) if want to use a minikube cluster or [this one](https://github.com/ufcg-lsd/klue/tree/main/docs/#eks) if you want to use an EKS cluster.

### 📌 Install Dependencies and Submodules
With the cluster ready (or your environment to create one), you need to install the required dependencies and submodules:

1. **Python3 Libraries** – Install the necessary libraries as listed in the requirements.txt. If necessary, you can create a venv.
```bash
python3 -m pip install -r requirements.txt
```

2. **Git Submodules** – After this, init the submodule repositories `prometheus` and `karpenter-code` using
```bash
git submodule update --init --recursive
```
---
## 📂 About the Emulation Input
Follow [this guide](https://github.com/ufcg-lsd/klue/tree/main/docs/#INPUT) to learn how to prepare the input for KLUE. The input can be a trace collected from a real cluster or a trace you generate yourself, as long as it follows the format defined in our tool's documentation.

## 🚀 Executing the Emulation Tool

### 🔑 Grant Execution Permission
Before running an emulation, grant execution permission to the **execute_emulation.sh** file by running:

```bash
chmod +x execute-emulation.sh
```
### ▶️ Running the KLUE

Our emulation tool supports **15 different execution modes** by combining the available flags. Below are the main ways to run the tool, with examples for each scenario. You can combine the flags as needed to fit your use case.

Like you saw before, is possible to run our emulation tool in two different ways: using an existing cluster or creating a new one. The two readme files provided in [🛠 Installation Guide](#-installation-guide) describes more about the possibilities.

#### 0. **Before Start**
Now that you have decided the kind of cluster you want to use, you can create a new EKS cluster by using the flag **--new-cluster**:
```bash
./execute_emulation.sh --new-cluster <other arguments>
```
Or use an existing cluster independing of the kind (EKS, minikube or another) by running:
```bash
./execute_emulation.sh --use-cluster <cluster-context> <other arguments>
```

**OBS:** you can get the cluster context by running `kubectl config current-context`.

#### 1. **Basic Emulation with Existing Cluster**
Use an existing cluster and provide a trace file, it will start an emulation without Karpenter, dynamic infrastructure and workload, and consideer that you don't have and input in the KLUE format:
```bash
./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path>
```

#### 2. **Enable Karpenter (Dynamic Node Management)**
If you want to use Karpenter for dynamic node management, you need to provide the path to the nodepool file:
```bash
./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path> --use-karpenter --nodepool-path <nodepool-path>
```

#### 3. **Skip Tracer Step**
Like we said before in [📂 About the Emulation Input](#-about-the-emulation-input), you can execute our emulation tool in a lot of scenarious. One of them, is the one which you have one input in the format of our tool. 
Add `--skip-tracer` to any command to skip the trace generation step:
```bash
./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path> --skip-tracer
```

#### 5. **Static Infrastructure or Workload**
Use static infrastructure and/or workload:
```bash
./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path> --static-infra
./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path> --static-workload
./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path> --static-infra --static-workload
```

#### 6. **Development Mode**
Set up a development environment (no emulation):
```bash
./execute_emulation.sh --dev --use-cluster <cluster-context>
./execute_emulation.sh --dev --new-cluster
```
You can also combine with `--use-karpenter` if needed (it will install the karpenter in your cluster).

---

#### ℹ️ **Combining Flags**
You can combine the flags above to create up to 15 different execution modes, for example:
- Emulation with new cluster, Karpenter, static infra, and skip tracer:
  ```bash
  ./execute_emulation.sh --sim --new-cluster --data-path <trace-path> --use-karpenter --nodepool-path <nodepool-path> --static-infra --skip-tracer
  ```
- Emulation with existing cluster, dynamic infra, and workload:
  ```bash
  ./execute_emulation.sh --sim --use-cluster <cluster-context> --data-path <trace-path>
  ```

#### 7. **Help**
To see all available options and combinations, run:
```bash
./execute_emulation.sh --help
```

> **Note:** Some flags require others (e.g., `--use-karpenter` requires `--nodepool-path`). If you provide invalid or missing combinations, the script will show an error message.

---
## 🧪 Example of Tool Execution
![Demo do KLUE](assets/emulation-running.gif)

---
## ⚠️ Important Precautions

When running the emulation multiple times on the same cluster, that are **three main steps** needed for guaranteeing that you will have a correct execution, these are:

- **Removing all nodepools:**
```bash
kubectl delete nodepools --all
```

- **Cleaning the /tmp:**
```bash
rm /tmp/*.csv
rm /tmp/*.json
```

- **Deleting all deployments (depending of your input):**
```bash
kubectl delete deployments -A --all
kubectl delete no --all
```

---
## 👥 Team
- **Kayky Fidelis – Undergraduate Student, Federal University of Campina Grande (UFCG)** – [LinkedIn](https://www.linkedin.com/in/kayky-fidelis/)  
- **Geraldo Sobreira – Undergraduate Student, Federal University of Campina Grande (UFCG)** – [LinkedIn](https://www.linkedin.com/in/geraldo-sobreira-junior/)  
- **Eric Matozo – Master's Student, Federal University of Campina Grande (UFCG)** – [LinkedIn](https://www.linkedin.com/in/ericmatozo/)  

## 👨‍🏫 Supervised by  
- **Giovanni Farias – PhD, Federal University of Campina Grande (UFCG)**  
- **Fábio Morais – PhD, Federal University of Campina Grande (UFCG)**  