#!/bin/bash

kubectl delete nodepools --all
kubectl delete deployments -A --all

rm -rf /tmp/*csv
rm -rf /tmp/output_objects.json

kill $(ps aux | grep 30222)
