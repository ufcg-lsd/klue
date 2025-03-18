go install github.com/google/ko@latest
export PATH=$PATH:~/go/bin
source ~/.bashrc

# Setup Prometheus and Grafana

helm install prometheus prometheus-community/kube-prometheus-stack -f values.yaml --namespace kube-system

cd karpenter-code

make toolchain
make build
make install-kwok
make apply
make gen_instance_types

kubectl get po -A

cd ..

kubectl apply -f configuration-files/karpenter-servicemonitor.yml

while [[ $(kubectl get pod prometheus-prometheus-kube-prometheus-prometheus-0 -n kube-system -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 5
done

