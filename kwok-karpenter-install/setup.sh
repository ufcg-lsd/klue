go install github.com/google/ko@latest
export PATH=$PATH:~/go/bin
source ~/.bashrc

# Setup Prometheus and Grafana

kubectl create namespace monitoring

kubectl apply --server-side -f kube-prometheus/manifests/setup
kubectl wait \
	--for condition=Established \
	--all CustomResourceDefinition \
	--namespace=monitoring
kubectl apply -f kube-prometheus/manifests/

cd karpenter-code

make toolchain
make build
make install-kwok
make apply
make gen_instance_types

kubectl get po -A

cd ..

kubectl apply -f configuration-files/karpenter-servicemonitor.yml
./install-kwok.sh

while [[ $(kubectl get pod prometheus-k8s-0 -n monitoring -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 5
done

# ID 6417
# Access Prometheus
# kubectl port-forward --address 0.0.0.0 pod/prometheus-k8s-0  30222:9090 -n monitoring &
# Access Grafana
# kubectl port-forward --address 0.0.0.0 pod/my-prometheus-grafana-{hash}  3000:3000 -n monitoring &
# kubectl get secret my-prometheus-grafana -n monitoring -o jsonpath="{.data.admin-password}" | base64 --decode; echo
