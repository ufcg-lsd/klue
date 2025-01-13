#!/bin/bash

kubectl apply -f yamls/rbac.yaml
kubectl apply -f yamls/rb.yaml
kubectl apply -f yamls/nginx.yaml
kubectl apply -f yamls/nginx2.yaml
kubectl get po --all-namespaces
kubectl apply -f yamls/kube-scheduler.yaml
kubectl apply -f yamls/kwok-node.yaml
