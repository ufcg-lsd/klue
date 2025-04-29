#!/bin/bash

PODS_AND_NODES_MAP="/tmp/pods_and_nodes_map.csv"

NUM_PODS_TO_SCHEDULE=$(($(wc -l < "$PODS_AND_NODES_MAP") - 1))

INITIAL_PENDING_PODS=$(kubectl get pods --all-namespaces --field-selector=status.phase=Pending --no-headers | wc -l)

DESIRED_PENDING_PODS=$((INITIAL_PENDING_PODS - NUM_PODS_TO_SCHEDULE))

cd ./custom-k8s-scheduler

while [ ! -f "$PODS_AND_NODES_MAP" ]; do
    echo "Aguardando o arquivo $PODS_AND_NODES_MAP ser criado..."
    sleep 2
done

cp "$PODS_AND_NODES_MAP" .
if [ ! -f ./custom-scheduler ]; then
	echo "[SCHEDULER] [INFO] Compiling scheduler code"
	CGO_ENABLED=0 go build -o custom-scheduler .
else
    echo "[SCHEDULER] [INFO] Binary already exists. Skipping build."
fi

./custom-scheduler &

SCHEDULER_PID=$!

echo "[SCHEDULER] [INFO] Scheduler started with PID: $SCHEDULER_PID"

while true; do
    CURRENT_PENDING_PODS=$(kubectl get pods --all-namespaces --field-selector=status.phase=Pending --no-headers | wc -l)

    if [ "$CURRENT_PENDING_PODS" -eq "$DESIRED_PENDING_PODS" ]; then
        echo "[SCHEDULER] [INFO] All initial pending pods have been scheduled. Killing scheduler."
        kill $SCHEDULER_PID
        break
    fi

    echo "[SCHEDULER] [INFO] There are still $CURRENT_PENDING_PODS pending pods. Expected $DESIRED_PENDING_PODS pending pods. Checking again in 30 seconds..."
    sleep 10
done

bash default-script.sh

rm ./pods_and_nodes_map.csv
