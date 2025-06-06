package main

import (
	"bufio"
	"context"
	"os"
	"strings"
	"sync"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/fields"
	"k8s.io/client-go/informers"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/tools/cache"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/klog/v2"
)

type PodScheduler struct {
	clientset        *kubernetes.Clientset
	podNodeMapping   map[string]PodNodeMapping
	retryQueue       chan *corev1.Pod
	retryQueueLock   sync.Mutex
}

type PodNodeMapping struct {
	NodeName  string
	Namespace string
}

type DefaultBinder struct {
	handle *kubernetes.Clientset
}

func (b DefaultBinder) Bind(ctx context.Context, p *corev1.Pod, nodeName string, namespace string) error {
	logger := klog.FromContext(ctx)
	logger.V(3).Info("Attempting to bind pod to node", "pod", klog.KObj(p), "node", klog.KRef("", nodeName))
	binding := &corev1.Binding{
		ObjectMeta: metav1.ObjectMeta{Namespace: namespace, Name: p.Name, UID: p.UID},
		Target:     corev1.ObjectReference{Kind: "Node", Name: nodeName},
	}
	err := b.handle.CoreV1().Pods(namespace).Bind(ctx, binding, metav1.CreateOptions{})
	if err != nil {
		logger.Error(err, "Failed to bind pod", "pod", klog.KObj(p), "node", klog.KRef("", nodeName))
	} else {
		logger.Info("Successfully bound pod", "pod", klog.KObj(p), "node", klog.KRef("", nodeName))
	}
	return err
}

func main() {
	// Load the kubeconfig file for local access
	kubeconfig := os.Getenv("KUBECONFIG")
	if kubeconfig == "" {
		kubeconfig = clientcmd.RecommendedHomeFile // Default to ~/.kube/config
	}
	klog.Info("Using kubeconfig file:", kubeconfig)

	config, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
	if err != nil {
		klog.Fatalf("Failed to build kubeconfig: %v", err)
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		klog.Fatalf("Failed to create Kubernetes client: %v", err)
	}

	klog.Info("Successfully connected to the Kubernetes API")

	podNodeMapping, err := loadPodNodeMapping("./pods_and_nodes_map.csv")
	if err != nil {
		klog.Fatalf("Error loading pod node mappings: %v", err)
	}

	klog.Info("Loaded pod node mappings, starting scheduler")

	scheduler := &PodScheduler{
		clientset:      clientset,
		podNodeMapping: podNodeMapping,
		retryQueue:     make(chan *corev1.Pod, 100), // buffer of 100 pods
	}

	binder := DefaultBinder{handle: clientset}

	factory := informers.NewSharedInformerFactoryWithOptions(clientset, 0,
		informers.WithTweakListOptions(func(options *metav1.ListOptions) {
			options.FieldSelector = fields.OneTermEqualSelector("spec.nodeName", "").String()
		}),
	)

	podInformer := factory.Core().V1().Pods().Informer()

	podInformer.AddEventHandler(cache.ResourceEventHandlerFuncs{
		AddFunc: func(obj interface{}) {
			pod := obj.(*corev1.Pod)
			klog.Infof("Pod added: %s/%s", pod.Namespace, pod.Name)
			scheduler.SchedulePod(pod, binder)
		},
	})

	go scheduler.retryScheduler(binder) // Start the retry scheduler

	stop := make(chan struct{})
	defer close(stop)
	factory.Start(stop)
	factory.WaitForCacheSync(stop)

	select {}
}

func (s *PodScheduler) SchedulePod(pod *corev1.Pod, binder DefaultBinder) {
	klog.Infof("Scheduling pod: %s/%s", pod.Namespace, pod.Name)
	if mapping, ok := s.podNodeMapping[pod.Name]; ok {
		klog.Infof("Found node mapping for pod: %s -> %s", pod.Name, mapping.NodeName)
		err := binder.Bind(context.Background(), pod, mapping.NodeName, mapping.Namespace)
		if err != nil {
			klog.Errorf("Failed to bind pod %s to node %s in namespace %s: %v", pod.Name, mapping.NodeName, mapping.Namespace, err)
			s.retryQueue <- pod // Add to retry queue
		}
	} else {
		klog.Warningf("No node mapping found for pod %s", pod.Name)
	}
}

func (s *PodScheduler) retryScheduler(binder DefaultBinder) {
	for {
		select {
		case pod := <-s.retryQueue:
			klog.Infof("Retrying scheduling for pod: %s/%s", pod.Namespace, pod.Name)
			s.SchedulePod(pod, binder) // Attempt to schedule again
			time.Sleep(1 * time.Minute) // Wait a minute before next retry
		}
	}
}

func loadPodNodeMapping(filePath string) (map[string]PodNodeMapping, error) {
	klog.Infof("Loading pod node mappings from file: %s", filePath)
	file, err := os.Open(filePath)
	if err != nil {
		klog.Errorf("Failed to open pod node mapping file: %v", err)
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	podNodeMap := make(map[string]PodNodeMapping)
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.Split(line, ",")
		if len(parts) != 3 {
			klog.Warningf("Skipping invalid line in mapping file: %s", line)
			continue
		}
		podName := strings.TrimSpace(parts[0])
		nodeName := strings.TrimSpace(parts[2])
		namespace := strings.TrimSpace(parts[1])
		podNodeMap[podName] = PodNodeMapping{
			NodeName:  nodeName,
			Namespace: namespace,
		}
	}

	if err := scanner.Err(); err != nil {
		klog.Errorf("Error reading mapping file: %v", err)
		return nil, err
	}

	klog.Infof("Successfully loaded %d pod node mappings", len(podNodeMap))
	return podNodeMap, nil
}
