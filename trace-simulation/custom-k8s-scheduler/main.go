package main

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/fields"
	"k8s.io/client-go/informers"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/cache"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/klog/v2"
)

type PodScheduler struct {
	clientset        *kubernetes.Clientset
	podNodeMapping   map[string]string
	retryQueue       chan *corev1.Pod
	retryQueueLock   sync.Mutex
}

type DefaultBinder struct {
	handle *kubernetes.Clientset
}

func (b DefaultBinder) Bind(ctx context.Context, p *corev1.Pod, nodeName string) error {
	logger := klog.FromContext(ctx)
	logger.V(3).Info("Attempting to bind pod to node", "pod", klog.KObj(p), "node", klog.KRef("", nodeName))
	binding := &corev1.Binding{
		ObjectMeta: metav1.ObjectMeta{Namespace: p.Namespace, Name: p.Name, UID: p.UID},
		Target:     corev1.ObjectReference{Kind: "Node", Name: nodeName},
	}
	return b.handle.CoreV1().Pods(binding.Namespace).Bind(ctx, binding, metav1.CreateOptions{})
}

func main() {
    config, err := clientcmd.BuildConfigFromFlags("", clientcmd.RecommendedHomeFile)
    if err != nil {
	    config, err = rest.InClusterConfig()
	    if err != nil {
		    panic(err.Error())
	    }
    }

    // Disable certificate verification
    config.TLSClientConfig.Insecure = true
    config.TLSClientConfig.CAFile = ""

    clientset, err := kubernetes.NewForConfig(config)
    if err != nil {
	    panic(err.Error())
    }

    fmt.Println("Successfully connected to the Kubernetes API")

	podNodeMapping, err := loadPodNodeMapping("/usr/local/bin/pod_node_mapping.csv")
	if err != nil {
		panic(fmt.Sprintf("Error loading pod node mappings: %v", err))
	}

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
			scheduler.SchedulePod(pod, binder)
		},
	})

	go scheduler.retryScheduler(binder)  // Start the retry scheduler

	stop := make(chan struct{})
	defer close(stop)
	factory.Start(stop)
	factory.WaitForCacheSync(stop)

	select {}
}

func (s *PodScheduler) SchedulePod(pod *corev1.Pod, binder DefaultBinder) {
	if nodeName, ok := s.podNodeMapping[pod.Name]; ok {
		err := binder.Bind(context.Background(), pod, nodeName)
		if err != nil {
			fmt.Printf("Failed to bind pod %s to node %s: %v\n", pod.Name, nodeName, err)
			s.retryQueue <- pod // Add to retry queue
		}
	}
}

func (s *PodScheduler) retryScheduler(binder DefaultBinder) {
	for {
		select {
		case pod := <-s.retryQueue:
			fmt.Println("Retrying scheduling for pod:", pod.Name)
			s.SchedulePod(pod, binder) // Attempt to schedule again
			time.Sleep(1 * time.Minute) // Wait a minute before next retry
		}
	}
}

func loadPodNodeMapping(filePath string) (map[string]string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	podNodeMap := make(map[string]string)
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.Split(line, ",")
		if len(parts) != 2 {
			continue
		}
		podNodeMap[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	return podNodeMap, nil
}

