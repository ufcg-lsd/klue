#!/bin/bash

kubectl apply -f yamls/rbac.yaml
kubectl apply -f yamls/rb.yaml
kubectl apply -f yamls/kube-scheduler.yaml
