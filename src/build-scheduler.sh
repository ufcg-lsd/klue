#!/bin/bash

PODS_AND_NODES_MAP="/tmp/pods_and_nodes_map.csv"

NUM_PODS_TO_SCHEDULE=$(($(wc -l < "$PODS_AND_NODES_MAP") - 1))

INITIAL_PENDING_PODS=$(kubectl get pods --all-namespaces --field-selector=status.phase=Pending --no-headers | wc -l)

DESIRED_PENDING_PODS=$((INITIAL_PENDING_PODS - NUM_PODS_TO_SCHEDULE))

cd ./src/custom-k8s-scheduler

while [ ! -f "$PODS_AND_NODES_MAP" ]; do
    echo "[SCHEDULER] [INFO] Waiting $PODS_AND_NODES_MAP file be created..."
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

# for each pod in pods_and_nodes_map, check if it's scheduled
all_initial_pods_scheduled () {
    while IFS=',' read -r pod namespace	node
    do
      # skip empty lines and headers
      [[ -z "$pod" || -z "$namespace" ]] && continue
      [[ "$pod" == "pod" && "$namespace" == "namespace" ]] && continue  
    
      node_name=$(kubectl -n "$namespace" get pod "$pod" -o jsonpath='{.spec.nodeName}')
      if [[ -z "$node_name" ]]; then
          echo "[SCHEDULER] [WARN] $pod has not been scheduled yet."
          return 1
      fi
    done < "$PODS_AND_NODES_MAP"
    
    return 0
}

while true; do
    if all_initial_pods_scheduled; then
        echo "[SCHEDULER] [INFO] All initial pending pods have been scheduled. Killing scheduler."
        kill "$SCHEDULER_PID"
        break
    fi

    echo "[SCHEDULER] [INFO] Not all initial pods were scheduled. Checking again in 10 seconds..."
    sleep 10
done

bash default-script.sh

rm ./pods_and_nodes_map.csv
