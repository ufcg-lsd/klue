#!/bin/bash
set -e

echo "▶ Installing VPA"
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
cd ../../
echo "✅ VPA installed"

echo "▶ Patching kube-state-metrics ClusterRole to read VPAs"
kubectl patch clusterrole kube-state-metrics --type=json -p='[
  {
    "op": "add",
    "path": "/rules/-",
    "value": {
      "apiGroups": ["autoscaling.k8s.io"],
      "resources": ["verticalpodautoscalers"],
      "verbs": ["list", "watch"]
    }
  },
  {
    "op": "add",
    "path": "/rules/-",
    "value": {
      "apiGroups": ["apiextensions.k8s.io"],
      "resources": ["customresourcedefinitions"],
      "verbs": ["list", "watch"]
    }
  }
]'

echo "▶ Patching kube-state-metrics Deployment with VPA CustomResourceStateMetrics"
kubectl patch deployment kube-state-metrics -n monitoring --type=json -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/args/-",
    "value": "--custom-resource-state-config=kind: CustomResourceStateMetrics\nspec:\n  resources:\n    - groupVersionKind:\n        group: autoscaling.k8s.io\n        kind: VerticalPodAutoscaler\n        version: v1\n      labelsFromPath:\n        verticalpodautoscaler: [metadata, name]\n        namespace: [metadata, namespace]\n        target_kind: [spec, targetRef, kind]\n        target_name: [spec, targetRef, name]\n      metrics:\n        - name: verticalpodautoscaler_status_recommendation_containerrecommendations_target\n          help: VPA target memory\n          each:\n            type: Gauge\n            gauge:\n              path: [status, recommendation, containerRecommendations]\n              valueFrom: [target, memory]\n              labelsFromPath:\n                container: [containerName]\n          commonLabels:\n            resource: memory\n            unit: byte\n        - name: verticalpodautoscaler_status_recommendation_containerrecommendations_lowerbound\n          help: VPA lowerBound memory\n          each:\n            type: Gauge\n            gauge:\n              path: [status, recommendation, containerRecommendations]\n              valueFrom: [lowerBound, memory]\n              labelsFromPath:\n                container: [containerName]\n          commonLabels:\n            resource: memory\n            unit: byte\n        - name: verticalpodautoscaler_status_recommendation_containerrecommendations_upperbound\n          help: VPA upperBound memory\n          each:\n            type: Gauge\n            gauge:\n              path: [status, recommendation, containerRecommendations]\n              valueFrom: [upperBound, memory]\n              labelsFromPath:\n                container: [containerName]\n          commonLabels:\n            resource: memory\n            unit: byte\n        - name: verticalpodautoscaler_status_recommendation_containerrecommendations_target\n          help: VPA target CPU\n          each:\n            type: Gauge\n            gauge:\n              path: [status, recommendation, containerRecommendations]\n              valueFrom: [target, cpu]\n              labelsFromPath:\n                container: [containerName]\n          commonLabels:\n            resource: cpu\n            unit: core\n        - name: verticalpodautoscaler_status_recommendation_containerrecommendations_lowerbound\n          help: VPA lowerBound CPU\n          each:\n            type: Gauge\n            gauge:\n              path: [status, recommendation, containerRecommendations]\n              valueFrom: [lowerBound, cpu]\n              labelsFromPath:\n                container: [containerName]\n          commonLabels:\n            resource: cpu\n            unit: core\n        - name: verticalpodautoscaler_status_recommendation_containerrecommendations_upperbound\n          help: VPA upperBound CPU\n          each:\n            type: Gauge\n            gauge:\n              path: [status, recommendation, containerRecommendations]\n              valueFrom: [upperBound, cpu]\n              labelsFromPath:\n                container: [containerName]\n          commonLabels:\n            resource: cpu\n            unit: core\n"
  }
]'

echo "▶ Waiting for kube-state-metrics to restart"
kubectl rollout status deployment/kube-state-metrics -n monitoring --timeout=120s

echo ""
echo "✅ VPA metrics available in Prometheus:"
echo "   - kube_customresource_verticalpodautoscaler_status_recommendation_containerrecommendations_target"
echo "   - kube_customresource_verticalpodautoscaler_status_recommendation_containerrecommendations_lowerbound"
echo "   - kube_customresource_verticalpodautoscaler_status_recommendation_containerrecommendations_upperbound"
echo ""
echo "▶ To verify, run:"
echo "   kubectl port-forward svc/prometheus-k8s -n monitoring 9090:9090"
echo "   curl -s 'http://localhost:9090/api/v1/query?query=kube_customresource_verticalpodautoscaler_status_recommendation_containerrecommendations_target' | jq '.data.result'"