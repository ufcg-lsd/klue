#!/bin/bash

sudo docker build -t sobreira155/emulation-scheduler:latest .
sudo docker push sobreira155/emulation-scheduler:latest
kubectl apply -f yamls/rbac.yaml
kubectl apply -f yamls/deploy.yaml
