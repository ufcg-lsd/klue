#!/bin/bash

cp /tmp/pods_and_nodes_map.csv custom-k8s-scheduler
docker build -t sobreira155/emulation-scheduler:latest custom-k8s-scheduler
docker push sobreira155/emulation-scheduler:latest
kubectl apply -f /home/geraldo/karpenter-research/trace-simulation/custom-k8s-scheduler/yamls/rbac.yaml
kubectl apply -f /home/geraldo/karpenter-research/trace-simulation/custom-k8s-scheduler/yamls/deploy.yaml
