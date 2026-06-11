"""
Manager class is responsible for managing Kubernetes resources and orchestrating the setup and execution
of a trace emulation process. It interacts with the Kubernetes API to manage namespaces, deployments,
nodeclaims, and other resources, while also handling custom logic for scaling and disruption times.
"""

import subprocess
import time
from datetime import datetime
from pods_mapping import PodsMapping
from collector import Collector
from workload.manager import WorkloadManager
from infrastructure.manager import InfrastructureManager
import threading

class Manager:
    """
    Manager class is responsible for managing Kubernetes resources and orchestrating the setup and execution
    of a trace emulation process. It interacts with the Kubernetes API to manage namespaces, deployments,
    nodeclaims, and other resources, while also handling custom logic for scaling and disruption times.
    Attributes:
        input_step (int): Time step interval for processing trace entries.
        data_path (string): The path of the JSON with the objects that will be applied by broker.
    """

    def __init__(self, data_path='/tmp', karpenter=True, infrastructure=None, workload=None, hpa=True):
        """
        Initializes the Manager class.
        """
        self.infrastructure = infrastructure
        self.workload = workload

        self.infrastructure_manager = InfrastructureManager(f"{data_path}/infrastructure_description.json", karpenter, infrastructure)
        self.workload_manager = WorkloadManager(f"{data_path}/workload_description.json", workload, hpa)

        self.pods_mapping = PodsMapping(karpenter)
        self.collector = Collector(step=30)

    def log(self, message):
        """
        Logs a message with a "[BROKER]" prefix.
        """
        print(f"[BROKER] {message}")

    def start_mapping_and_scheduler(self):
        """
        Starts the process of mapping pods and running the scheduler.

        This method performs the following actions:
        1. Executes the `run` method of the `pods_mapping` object to initiate pod mapping.
        2. Runs the `build-scheduler.sh` script using a subprocess call to set up the scheduler.
        """
        self.pods_mapping.run()
        subprocess.run(["bash", "src/build-scheduler.sh"], check=True)

    def collect_loop(self, start_time):
        """
        Periodically collects metrics and writes them to timestamped output
        files while the emulation is running.
    
        Args:
            start_time (int): Initial Unix timestamp used as the beginning
                of the first collection window.
        """

        interval = 60  # 60s
        safety_offset = 30    # 30s

        current = start_time


        run_id = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
        output_dir = f"output_csv_{run_id}"

        self.log(f"[INFO] Using output dir: {output_dir}")
        self.log("[INFO] Continuous collection started")

        while not self.stop_collection:
            time.sleep(interval)

            end_time = int(time.time())

            self.log(f"[INFO] Collecting: {current} → {end_time}")

            self.collector.collect(
                start_time=current,
                end_time=end_time,
                output_dir=output_dir
            )

            current = end_time + safety_offset

    def run(self):
        """
        Executes the main workflow of the Broker.

        This method orchestrates the entire lifecycle of the Broker's operation.
        """
        self.log("[INFO] Starting Broker.")

        collector_thread = None

        try:
            self.log("[INFO] Preparing to start emulation.")
            self.infrastructure_manager.before_setup()
            self.workload_manager.before_setup()

            self.log("[INFO] Executing setup of infrastructure and workload.")
            self.infrastructure_manager.setup()

            self.workload_manager.setup()

            self.start_mapping_and_scheduler()

            self.workload_manager.before_emulation()
            self.infrastructure_manager.before_emulation()

            self.log("[INFO] Starting emulation.")
            start = datetime.now()

            # 1. Criar as threads para os métodos de emulação
            infra_emulation_thread = threading.Thread(
                target=self.infrastructure_manager.emulation,
                name="InfraEmulationThread"
            )
            workload_emulation_thread = threading.Thread(
                target=self.workload_manager.emulation,
                name="WorkloadEmulationThread"
            )

            start_time = int(datetime.now().timestamp())
            self.stop_collection = False

            collector_thread = threading.Thread(
                target=self.collect_loop,
                args=(start_time,),
                name="CollectorThread"
            )

            self.log("[INFO] Starting collector thread")
            collector_thread.start()
            duration = int((datetime.now() - start).total_seconds() + 15)
            subprocess.run(["bash", "src/port-forward.sh"], check=True)

            self.log("[INFO] Starting emulation thread for InfrastructureManager.")
            infra_emulation_thread.start()
            self.log("[INFO] Starting emulation thread for WorkloadManager.")
            workload_emulation_thread.start()
        
            infra_emulation_thread.join()
            self.log("[INFO] InfrastructureManager emulation thread completed.")
            workload_emulation_thread.join()
            self.log("[INFO] WorkloadManager emulation thread completed.")

        finally:
            self.stop_collection = True

            if collector_thread:
                collector_thread.join()
                self.log("[INFO] Collector thread stopped.")

            self.log("[INFO] Emulation completed. Tearing down infrastructure, workload and temp files.")

            try:
                self.workload_manager.tear_down()
            except Exception:
                self.log("[ERROR] Failed to tear down workload. Traceback follows.")
                traceback.print_exc()

            try:
                self.infrastructure_manager.tear_down()
            except Exception:
                self.log("[ERROR] Failed to tear down infrastructure. Traceback follows.")
                traceback.print_exc()