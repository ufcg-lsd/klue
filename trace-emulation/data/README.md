# 🚀 KLUE Required Metrics for Infrastructure and Workload Manager

This document outlines the **Prometheus metrics** required when generating input for the **infrastructure and workload manager** using our KLUE solution. The following metrics are essential:

- 📊 `karpenter_pods_state`
- 🖥️ `kube_pod_container_resource_requests`
- 🔗 `kube_pod_owner`
- 🛠️ `kube_replicaset_owner`

## 📋 Metrics Overview

| **Metric**                      | **Description**                                                                                      | **Columns Needed**                                         |
|----------------------------------|------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| 🖥️ `karpenter_pods_state`           | Tracks the state of pods managed by Karpenter.                                                       | `timestamp`, `instance_type`, `node`, `pod`, `nodepool`, `phase` |
| 📊 `kube_pod_container_resource_requests` | Records resource requests (CPU, memory) made by each pod.                                       | `timestamp`, `pod`, `namespace`, `value`, `resource`, `node` |
| 🔗 `kube_pod_owner`                 | Identifies the owner of each pod (e.g., Deployment, ReplicaSet).                                    | `pod`, `owner_name`, `owner_kind`                           |
| 🛠️ `kube_replicaset_owner`          | Maps ReplicaSets to their owners (e.g., Deployments).                                                | `replicaset`, `owner_kind`, `owner_name`                    |

## 🔄 Data Processing Flow

The provided Python script performs the following operations:

1. 📥 **Loads CSV files** for each metric from the paths provided as command-line arguments.
2. 🧹 **Preprocesses data** by filtering and merging DataFrames based on `timestamp`, `pod`, and `node`.
3. 📊 **Aggregates resource usage** (CPU and memory) and removes irrelevant namespaces like `kube-system`.
4. 🔗 **Joins ownership data** from `kube_pod_owner` and `kube_replicaset_owner`.
5. 🛠️ **Generates output files** including `/tmp/final_trace.csv` and `/tmp/output_objects.json`.

## 📂 Output Files

- 📄 **/tmp/pods_allocation.csv**: Summary of pod allocation across nodes.
- 📊 **/tmp/final_trace.csv**: Final processed trace data with pod counts, CPU, memory usage, and actions.
- 🖥️ **/tmp/nodeclaims.csv**: Unique node claims generated from the allocation data.
- 🛠️ **/tmp/output_objects.json**: JSON file containing Kubernetes objects for setup and trace replay.

## ▶️ Running the Script

To run the script, provide paths to the required CSV files:

```bash
python3 tracer.py "$TRACE_PATH/kube_pod_container_resource_requests.csv" "$TRACE_PATH/karpenter_pods_state.csv" "$TRACE_PATH/kube_pod_owner.csv" "$TRACE_PATH/kube_replicaset_owner.csv"
```

This will produce the necessary CSVs and JSON files as outputs, ready for use in Kubernetes workload emulation with KLUE. 🚀

