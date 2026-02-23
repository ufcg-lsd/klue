go install github.com/google/ko@latest
export PATH=$PATH:~/go/bin
source ~/.zshrc

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

# -----------------------------
# Grafana configuration
# -----------------------------

echo "▶ Detecting Minikube IP"
MINIKUBE_IP=$(minikube ip)

if [ -z "$MINIKUBE_IP" ]; then
  echo "❌ Failed to get Minikube IP"
  exit 1
fi

export MINIKUBE_IP
echo "▶ Minikube IP: $MINIKUBE_IP"

echo "▶ Applying Grafana ConfigMap"
envsubst < configuration-files/grafana/grafana-configmap.yml | kubectl apply -f -

echo "▶ Applying Grafana NodePort Service"
kubectl apply -f configuration-files/grafana/grafana-service-nodeport.yml

echo "▶ Restarting Grafana"
kubectl -n monitoring rollout restart deployment grafana

kubectl -n monitoring wait \
  --for=condition=available \
  deployment/grafana \
  --timeout=180s

echo ""
echo "✅ Grafana is ready!"
echo "👉 Open: http://${MINIKUBE_IP}:32000"
