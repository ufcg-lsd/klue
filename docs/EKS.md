# Creating or setting up an EKS Cluster
This guide will help you set up your environment to create and EKS cluster.
---

## 📌 Environment Variables

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

And then, replace the values in the `.env` file with your own values like the table above describes.