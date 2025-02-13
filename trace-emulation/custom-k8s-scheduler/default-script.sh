#!/bin/bash

kubectl apply -f yamls/rbac.yaml
kubectl apply -f yamls/rb.yaml
kubectl get po --all-namespaces
kubectl apply -f yamls/kube-scheduler.yaml
