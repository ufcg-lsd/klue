# Welcome to the VtexLab tool to configure and test Calico and Karpenter installation into an cluster EKS
This tools aims to assist in the installation and configuration of **EKS clusters** with **Calico** and **Karpenter**. Additionally, it provides a cost-effective way for developers to test changes in Karpenter's code without incurring unnecessary expenses.

## Setting up your cluster environment
Before starting to work with your cluster or testing code changes, follow these steps to properly set up your environment.

### Install Dependencies
To create your cluster with the Calico and Karpenter configured, you need to install some dependencies on your machine.

1. Install the EKSCTL following this [tutorial](https://eksctl.io/installation/)
2. Install the KUBECTL following this [tutorial](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
3. Install the AWS CLI following this [tutorial](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
4. Install the HELM package manager for K8S following this [tutorial](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
5. Set your aws sso configurations following this [tutorial](https://www.notion.so/vtexhandbook/Configure-AWS-SSO-02f86cdbbf4c4e50bbd2c251e4912c79)

We are providing you a short tutorial about the ENV variables:

- **CLUSTER_NAME**: The name of your cluster.
- **REGION**: AWS Region name
- **ENVIRONMENT**: the environment is a tag that will be used in your ASG
- **PRODUCT**: Product Tag
- **APPLICATION_NAME**: required tag to create the ASG
- **AWS_PROFILE**: AWS SSO profile name
- **CLUSTER_CONFIG_FILE**: The path of the cluster configuration file
- **NODEGROUP_CONFIG_FILE**: The path of the nodegroup configuration file
- **NODECLASS_CONFIG_FILE**: The path of the nodeclass configuration file
- **NODEPOOL_CONFIG_FILE**: The path of the nodepool configuration file
- **CALICO_CONFIG_FILE**: The path of the calico configuration file
- **CLUSTER_CNI**: You can set this variable to 'AmazonVPC' for using VPC CNI or to 'Calico' for using Calico CNI
- **QUEUE_NAME**: If you don't want to use an existing queue, set to another name
- **KARPENTER_VERSION**: Karpenter Version
- **KARPENTER_NAMESPACE**: The namespace to install Karpenter
- **CALICO_NAMESPACE**: The namespace to install Calico

Once you have these dependencies installed, you need to copy the `env.example` file to your `.env` using
```
cp .env.example .env
```

**(optional)** if you want to test the karpenter code, init the submodule repositories `gotrace` and `karpenter-code` using
```
git submodule update --init --recursive
```

## How to Create a Cluster With Calico and Karpenter Automatically
Add permission to execute the script
```
chmod +x create_cluster.sh
```
### Run the script
You can run the script to create your cluster using
```
./create_cluster.sh
```
## How to Delete a Cluster Automatically
To delete your cluster, add the permission to execute the script
```
chmod +x create_cluster.sh
```
Then, you can run the following command
```
./delete_cluster.sh
```

## Extra Links
Karpenter NodePool and NodeClass nice configuration examples to experiments can be checked in this [link](https://github.com/aws/karpenter-provider-aws/tree/v0.37.1/examples/v1beta1).

To check if the Calico Policies is working correctly in your cluster follow this [link](https://docs.tigera.io/calico/latest/network-policy/get-started/calico-policy/calico-policy-tutorial).