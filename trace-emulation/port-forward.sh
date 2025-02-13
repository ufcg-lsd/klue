while [[ $(kubectl get pod prometheus-k8s-0 -n monitoring -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 5
done

kubectl port-forward --address 0.0.0.0 pod/prometheus-k8s-0  30222:9090 -n monitoring &
