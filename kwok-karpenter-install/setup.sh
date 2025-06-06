go install github.com/google/ko@latest
export PATH=$PATH:~/go/bin
source ~/.bashrc

if [ $# -lt 1 ]; then
	echo "Uso: $0 <karpenter-on/karpenter-off>"
	exit 1
fi

KARPENTER="$1"

# Setup Prometheus and Grafana

kubectl create namespace monitoring

kubectl apply --server-side -f kube-prometheus/manifests/setup
kubectl wait \
	--for condition=Established \
	--all CustomResourceDefinition \
	--namespace=monitoring
kubectl apply -f kube-prometheus/manifests/

docker login

if [ "$KARPENTER" = "karpenter-on" ]; then
	cd karpenter-code

	make toolchain
	make build
	make install-kwok
	make apply
	make gen_instance_types

	cd ..

	kubectl apply -f configuration-files/karpenter-servicemonitor.yml
fi

./install-kwok.sh

while [[ $(kubectl get pod prometheus-k8s-0 -n monitoring -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 5
done
