# 🚀 KLUE INPUT

There are two ways to provide input to KLUE:

1. **Using a trace collected from a real Kubernetes cluster**
2. **Creating the emulation input yourself**, by generating the time series and the Kubernetes objects that KLUE will replay

This document describes the current format expected by the code in `src/tracer`, `src/workload/manager.py`, `src/infrastructure/manager.py`, and `src/pods_mapping.py`.

## 📂 Option 1: Input from collected metrics

When you use collected metrics, you pass the trace directory with `--data-path`. If `--skip-tracer` is **not** used, KLUE will read the collected files and generate:

- `/tmp/workload_description.json`
- `/tmp/infrastructure_description.json`
- `/tmp/pods_allocation.csv`

Those generated files are the ones consumed by the emulation managers.

### For an emulation **with Karpenter**

The directory passed in `--data-path` must contain:

- `kube_pod_container_resource_requests.csv`
- `karpenter_pods_state.csv`
- `kube_pod_owner.csv`
- `kube_replicaset_owner.csv`
- `instance_types.json`

If you use `--use-karpenter`, you must also pass:

- `--nodepool-path <nodepool-yaml>`

### For an emulation **without Karpenter**

The directory passed in `--data-path` must contain:

- `kube_pod_container_resource_requests.csv`
- `kube_pod_container_resource_limits.csv`
- `container_cpu_usage_seconds_total.csv`
- `container_memory_usage_bytes.csv`
- `kube_pod_owner.csv`
- `kube_pod_status_phase.csv`
- `kube_replicaset_owner.csv`
- `instance_types.json`
- `kube_horizontalpodautoscaler_spec_max_replicas.csv`
- `kube_horizontalpodautoscaler_spec_min_replicas.csv`
- `kube_horizontalpodautoscaler_spec_target_metric.csv`

These files reflect the current inputs used by `src/main.py` and `src/tracer/tracer_kwok.py`.

## 📂 Option 2: Creating the input yourself

If you want to build the input manually, the current flow expects you to prepare the generated files directly and run the emulation with `--skip-tracer`.

In practice, that means preparing:

- `/tmp/workload_description.json`
- `/tmp/infrastructure_description.json`
- `/tmp/pods_allocation.csv`

And then running something like:

```bash
./execute-emulation.sh --sim --use-cluster <cluster-context> --data-path <any-required-path> --skip-tracer
```

> **Note:** `--data-path` is still required by the current CLI validation even when `--skip-tracer` is used.

## 📄 Current structure of `infrastructure_description.json`

This file is read by `InfrastructureManager`.

Top-level structure:

```json
{
  "setup": [],
  "emulation": []
}
```

### `setup`

- Type: `list`
- Each entry is a full Kubernetes object applied during the setup phase

Current behavior:

- In the **non-Karpenter** path, these objects are usually `Node` manifests.
- In the **Karpenter** path, these objects are usually `NodeClaim` manifests.

Example:

```json
{
  "setup": [
    {
      "apiVersion": "v1",
      "kind": "Node",
      "metadata": {
        "name": "ip-172-16-16-126.ec2.internal"
      },
      "spec": {},
      "status": {}
    }
  ],
  "emulation": [
    {
      "timestamp": 300,
      "applied_objects": [],
      "deleted_objects": []
    }
  ]
}
```

### `emulation`

- Type: `list`
- Each entry must contain:
  - `timestamp`: integer, in seconds from the beginning of the emulation
  - `applied_objects`: list of full infrastructure objects to create at that timestamp
  - `deleted_objects`: list of node names to delete at that timestamp

Current example:

```json
{
  "timestamp": 600,
  "applied_objects": [
    {
      "apiVersion": "v1",
      "kind": "Node",
      "metadata": {
        "name": "ip-172-16-20-10.ec2.internal"
      },
      "spec": {},
      "status": {}
    }
  ],
  "deleted_objects": [
    "ip-172-16-16-126.ec2.internal"
  ]
}
```

## 📄 Current structure of `workload_description.json`

This file is read by `WorkloadManager`.

Top-level structure:

```json
{
  "setup": {
    "applied_objects": {},
    "workload_actions": []
  },
  "emulation": []
}
```

This is one of the main differences from the old documentation. The current code expects `setup.applied_objects` and `setup.workload_actions`.

### `setup.applied_objects`

- Type: `object`
- Keys: namespaces
- Values: lists of Kubernetes workload manifests

The workload generator currently creates Deployments, and HPA manifests can also appear in the same namespace list when HPA is enabled.

Example:

```json
{
  "setup": {
    "applied_objects": {
      "default": [
        {
          "apiVersion": "apps/v1",
          "kind": "Deployment",
          "metadata": {
            "name": "checkout",
            "namespace": "default"
          },
          "spec": {
            "replicas": 3,
            "selector": {
              "matchLabels": {
                "app": "fake-pod",
                "deployment": "checkout"
              }
            },
            "template": {
              "metadata": {
                "labels": {
                  "app": "fake-pod",
                  "deployment": "checkout"
                }
              },
              "spec": {
                "schedulerName": "custom-scheduler",
                "containers": [
                  {
                    "name": "checkout",
                    "image": "fake-image"
                  }
                ]
              }
            }
          }
        },
        {
          "apiVersion": "autoscaling/v2",
          "kind": "HorizontalPodAutoscaler",
          "metadata": {
            "name": "checkout",
            "namespace": "default"
          },
          "spec": {
            "scaleTargetRef": {
              "apiVersion": "apps/v1",
              "kind": "Deployment",
              "name": "checkout"
            },
            "minReplicas": 2,
            "maxReplicas": 10
          }
        }
      ]
    },
    "workload_actions": []
  },
  "emulation": []
}
```

### `setup.workload_actions`

- Type: `list`
- Supported action types currently used by the code:
  - `scale`
  - `set-usage`

#### `scale`

Used by `WorkloadManager.scale_workload()` when HPA is disabled.

Example:

```json
{
  "name": "checkout",
  "namespace": "default",
  "pods": 5,
  "kind": "deployment",
  "action": "scale"
}
```

#### `set-usage`

Used by `UsageManager` to assign pod CPU and memory usage during the emulation.

Example:

```json
{
  "name": "checkout",
  "namespace": "default",
  "action": "set-usage",
  "pods": {
    "checkout-abc123": {
      "cpu": 0.42,
      "memory": 268435456
    },
    "checkout-def456": {
      "cpu": 0.39,
      "memory": 260000000
    }
  }
}
```

### `emulation`

- Type: `list`
- Each entry must contain:
  - `timestamp`
  - `applied_objects`
  - `deleted_objects`
  - `workload_actions`

Example:

```json
{
  "timestamp": 300,
  "applied_objects": {
    "default": [
      {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
          "name": "search",
          "namespace": "default"
        },
        "spec": {
          "replicas": 2
        }
      }
    ]
  },
  "deleted_objects": [
    {
      "name": "checkout",
      "namespace": "default",
      "kind": "Deployment"
    }
  ],
  "workload_actions": [
    {
      "name": "search",
      "namespace": "default",
      "pods": 4,
      "kind": "deployment",
      "action": "scale"
    }
  ]
}
```

## 📄 Current structure of `pods_allocation.csv`

This file is read by `PodsMapping`.

It maps the original node allocation from the input to the fake nodes created in the emulation cluster.

### Without Karpenter

Expected columns:

- `namespace`
- `node`
- `replicaset`
- `owner_kind`
- `instance_type`
- `pods_count`

Example:

```csv
namespace,node,replicaset,owner_kind,instance_type,pods_count
default,ip-172-16-20-10.ec2.internal,checkout,Deployment,c6a.2xlarge,2
default,ip-172-16-20-11.ec2.internal,search,Deployment,c6a.2xlarge,1
```

### With Karpenter

Expected columns:

- `namespace`
- `node`
- `nodepool`
- `replicaset`
- `owner_kind`
- `instance_type`
- `pods_count`

Example:

```csv
namespace,node,nodepool,replicaset,owner_kind,instance_type,pods_count
default,ip-172-16-0-0.ec2.internal,default,checkout,Deployment,c6a.2xlarge,2
default,ip-172-16-0-1.ec2.internal,default,search,Deployment,c6a.2xlarge,1
```

## 📌 Practical notes

- `timestamp` values are interpreted as seconds from the start of the emulation.
- `deleted_objects` in workload entries must include enough information for `delete_object()` to identify the resource, especially `name`, `namespace`, and `kind`.
- If `--use-hpa` is enabled, HPA objects can be included in `applied_objects`, and HPA deletion entries can appear in `deleted_objects`.
- If HPA is enabled, regular `scale` actions are skipped by `WorkloadManager` and the autoscaling behavior should come from the HPA manifests and usage metrics.
- Infrastructure setup objects are also used to generate ServiceMonitors during execution.

## 📁 Examples in the repository

Examples live in:

- `docs/example/karpenter`
- `docs/example/default`

Some example files still reflect the older structure documented in the original `docs/INPUT.md`, so when in doubt, prefer the format described in this `v2` document and the current generator/manager code.