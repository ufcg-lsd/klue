while [[ $(kubectl get pod prometheus-prometheus-kube-prometheus-prometheus-0 -n kube-system -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 5
done

kubectl port-forward --address 0.0.0.0 pod/prometheus-prometheus-kube-prometheus-prometheus-0  30222:9090 -n kube-system &
