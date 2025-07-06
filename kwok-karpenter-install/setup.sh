go install github.com/google/ko@latest
export PATH=$PATH:~/go/bin
source ~/.bashrc

if [ $# -lt 1 ]; then
	echo "Uso: $0 <karpenter-on/karpenter-off>"
	exit 1
fi

KARPENTER="$1"
KUBERNETES_AUTOSCALER="$2"
CLUSTER_AUTOSCALER_PROVIDER_TEMPLATE="$3"

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

	echo "Instalando o KWOK"
	./install-kwok.sh

elif [ "$KUBERNETES_AUTOSCALER" = "kubernetes-autoscaler-on" ]; then
	if [ -z "$CLUSTER_AUTOSCALER_PROVIDER_TEMPLATE" ]; then
		echo "Erro: É necessário especificar --cluster-autoscaler-provider-template ao usar --use-kubernetes-autoscaler."
		exit 1
	fi

	echo "Instalndo o KOWK"
	./install-kwok.sh

	echo "Instalando o Kubernetes Cluster Autoscaler"

	kubectl apply -f configuration-files/kwok-provider-config.yaml
	
	kubectl annotate configmap kwok-provider-config \
		meta.helm.sh/release-name=autoscaler-kwok \
		meta.helm.sh/release-namespace=default --overwrite 
	
	kubectl label configmap kwok-provider-config \
		app.kubernetes.io/managed-by=Helm --overwrite

	kubectl apply -f ${CLUSTER_AUTOSCALER_PROVIDER_TEMPLATE}

	kubectl annotate configmap kwok-provider-templates \
		meta.helm.sh/release-name=autoscaler-kwok \
		meta.helm.sh/release-namespace=default --overwrite

	kubectl label configmap kwok-provider-templates \
		app.kubernetes.io/managed-by=Helm --overwrite

	cd autoscaler
	#cd /home/ubuntu/ca/autoscaler
	helm upgrade --install autoscaler-kwok charts/cluster-autoscaler \
		--namespace default \
		--set cloudProvider=kwok \
		--set image.tag="v1.32.1" \
		--set image.repository="registry.k8s.io/autoscaling/cluster-autoscaler" \
		--set extraArgs.v="4" \
		--set extraArgs.logtostderr="true" \
		--set extraArgs.stderrthreshold="info" \
		--set extraArgs.kubeconfig="/etc/kubeconfig/kwok.kubeconfig" \
		--set serviceMonitor.enabled=false \
		--set autoscalingGroups[0].name=dummy \
		--set autoscalingGroups[0].minSize=0 \
		--set autoscalingGroups[0].maxSize=5 \
		--set extraVolumeMounts[0].name=kwok-kubeconfig \
		--set extraVolumeMounts[0].mountPath="/etc/kubeconfig" \
		--set extraVolumeMounts[0].readOnly=true \
		--set extraVolumes[0].name=kwok-kubeconfig \
		--set extraVolumes[0].configMap.name=kwok-kubeconfig

	cd ..
	#cd /home/ubuntu/klue/kwok-karpenter-install

	while [[ $(kubectl get pod prometheus-k8s-0 -n monitoring -o jsonpath='{.status.phase}') != "Running" ]]; do
  		sleep 5
	done

	kubectl taint nodes klue-cluster-control-plane node-role.kubernetes.io/control-plane=:NoSchedule
else
	echo "Karpenter e Kubernetes Cluster Autoscaler estão desativados."
	echo "Instalando o KWOK"
	./install-kwok.sh
fi



while [[ $(kubectl get pod prometheus-k8s-0 -n monitoring -o jsonpath='{.status.phase}') != "Running" ]]; do
  sleep 5
done
