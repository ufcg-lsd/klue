#!/bin/bash

helm uninstall prometheus --namespace kube-system

kubectl delete deployments -A --all
kubectl delete nodepools --all
kubectl delete po -A --all

rm -rf /tmp/*csv
rm -rf /tmp/output_objects.json

kill $(ps aux | grep 30222)
