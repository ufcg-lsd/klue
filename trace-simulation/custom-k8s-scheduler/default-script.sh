#!/bin/bash

kubectl apply -f yamls/rbac.yaml
kubectl apply -f yamls/rb.yaml
kubectl apply -f yamls/nginx.yaml
kubectl get po --all-namespaces
kubectl apply -f yamls/ks.yaml
kubectl apply -f yamls/kwok-node.yaml



