#!/bin/bash

PODS_AND_NODES_MAP="/tmp/pods_and_nodes_map.csv"

cd ./custom-k8s-scheduler

while [ ! -f "$PODS_AND_NODES_MAP" ]; do
    echo "Aguardando o arquivo $PODS_AND_NODES_MAP ser criado..."
    sleep 2
done

cp "$PODS_AND_NODES_MAP" .
if [ ! -f ./custom-scheduler ]; then
	echo "Compiling scheduler code"
	CGO_ENABLED=0 go build -o custom-scheduler .
else
    echo "Binary already exists. Skipping build."
fi

./custom-scheduler &

SCHEDULER_PID=$!

echo "Scheduler started with PID: $SCHEDULER_PID"

while true; do
    PENDING_PODS=$(kubectl get pods --all-namespaces --field-selector=status.phase=Pending --no-headers | wc -l)

    if [ "$PENDING_PODS" -eq 0 ]; then
        echo "No pending pods found. Killing the scheduler process."
        kill $SCHEDULER_PID
        break
    fi

    echo "There are still $PENDING_PODS pending pods. Checking again in 30 seconds..."
    sleep 10
done

bash default-script.sh

rm ./pods_and_nodes_map.csv

#docker build -t sobreira155/emulation-scheduler:latest custom-k8s-scheduler
#docker push sobreira155/emulation-scheduler:latest
#kubectl apply -f /home/geraldo/karpenter-research/trace-emulation/custom-k8s-scheduler/yamls/rbac.yaml
#kubectl apply -f /home/geraldo/karpenter-research/trace-emulation/custom-k8s-scheduler/yamls/deploy.yaml
