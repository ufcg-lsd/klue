#!/bin/bash

set -e

print_step () {
  echo ""
  echo "--------------------------------------------------"
  echo "$1"
  echo "--------------------------------------------------"
  echo ""
  sleep 5
}

#################################################
print_step "Creating Cluster (Minikube)"
#################################################

chmod +x create-cluster.sh
printf "2\n" | ./create-cluster.sh

#################################################
print_step "Installing KWOK"
#################################################

cd kwok-karpenter-install
chmod +x setup.sh
./setup.sh karpenter-off
cd ..

#################################################
print_step "Setting Infrastructure and Workloads"
#################################################

cd testing-pod-usage

print_step "Creating KWOK Node"
kubectl apply -f node.yaml

print_step "Deploying Applications"
kubectl apply -f deployment.yaml

echo "Waiting for pods..."
kubectl wait --for=condition=Ready pod --all --timeout=120s

#################################################
print_step "Applying Monitoring and Usage Files"
#################################################

for node in $(kubectl get nodes -o jsonpath='{.items[*].metadata.name}'); do
  export NODE_NAME=$node
  envsubst < service-monitor.yaml | kubectl apply -f -
done

kubectl apply -f metric.yaml
kubectl apply -f cluster-usage.yaml

#################################################
print_step "Starting Prometheus Port-Forward (Background)"
#################################################

kubectl port-forward -n monitoring svc/prometheus-k8s 9090:9090 > /dev/null 2>&1 &
PROM_PID=$!

echo "Prometheus running (PID: $PROM_PID)"

#################################################
print_step "Enabling Metrics Server"
#################################################

minikube addons enable metrics-server

#################################################
print_step "Removing Default KWOK Usage Object"
#################################################

kubectl delete clusterresourceusage usage-from-annotation --ignore-not-found=true

#################################################
print_step "Installing VPA Requirements"
#################################################

cd ../autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
cd ../../testing-pod-usage

#################################################
print_step "Applying VPA and HPA"
#################################################

kubectl apply -f vpa.yaml
kubectl apply -f hpa.yaml

#################################################
print_step "Checking Current Resource Usage"
#################################################

sleep 200
kubectl top pod
kubectl top node

#################################################
print_step "Experiment Running 🚀"
#################################################

echo "Prometheus: http://localhost:9090"
echo "To stop port-forward: kill $PROM_PID"