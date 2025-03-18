#!/bin/bash

kubectl delete nodepools --all
kubectl delete deployments -A --all

rm -rf /tmp/*csv

#kill $(ps aux | grep 30322)
