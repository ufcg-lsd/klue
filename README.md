# Welcome to the automatic Calico and Karpenter installation into a cluster EKS

## How to Create a Cluster Automatically
### Install Dependencies
To create your cluster with the Calico and Karpenter configured, you need to install some dependencies in your machine.

1. Install the EKSCTL following this [tutorial](https://eksctl.io/installation/)
2. Install the KUBECTL following this [tutorial](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
3. Install the AWS CLI following this [tutorial](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
4. Install the HELM package manager for K8S following this [tutorial](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
5. Set your aws sso configurations following this [tutorial](https://www.notion.so/vtexhandbook/Configure-AWS-SSO-02f86cdbbf4c4e50bbd2c251e4912c79)

### Prepare the enviroment
When you have this dependencies installed, you need to copy the `env.example` file to your `.env` using
```
cp .env.example .env
```
Add the permission to execute the script
```
chmod +x create_cluster.sh
```
### Run the script
You can run the script to create your cluster using
```
./create_cluster.sh
```
## How to Delete a Cluster Automatically

## Extra Links
Karpenter NodePool and NodeClass examples can be checked in this [link](https://github.com/aws/karpenter-provider-aws/tree/v0.37.1/examples/v1beta1)