"""
Manager class is responsible for managing Kubernetes resources and orchestrating the setup and execution
of a trace emulation process. It interacts with the Kubernetes API to manage namespaces, deployments,
nodeclaims, and other resources, while also handling custom logic for scaling and disruption times.
"""

import subprocess
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

    def __init__(self, data_path='/tmp', karpenter=True, infrastructure=None, workload=None, emulation_name=None):
        """
        Initializes the Manager class.
        """
        self.infrastructure = infrastructure
        self.workload = workload
        self.emulation_name = emulation_name

        self.infrastructure_manager = InfrastructureManager(f"{data_path}/infrastructure_description.json", karpenter, infrastructure)
        self.workload_manager = WorkloadManager(f"{data_path}/workload_description.json", workload)

        self.pods_mapping = PodsMapping(karpenter)
        self.collector = Collector(step=30, emulation_name=emulation_name)

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

    def run(self):
        """
        Executes the main workflow of the Broker.

        This method orchestrates the entire lifecycle of the Broker's operation.
        """
        self.log("[INFO] Starting Broker.")
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

        self.log("[INFO] Starting emulation thread for InfrastructureManager.")
        infra_emulation_thread.start()
        self.log("[INFO] Starting emulation thread for WorkloadManager.")
        workload_emulation_thread.start()
    
        infra_emulation_thread.join()
        self.log("[INFO] InfrastructureManager emulation thread completed.")
        workload_emulation_thread.join()
        self.log("[INFO] WorkloadManager emulation thread completed.")

        duration = int((datetime.now() - start).total_seconds() + 15)
        subprocess.run(["bash", "src/port-forward.sh"], check=True)
        self.collector.collect(duration=duration)

        self.log("[INFO] Emulation completed. Tearing down infrastructure, workload and temp files.")
        self.infrastructure_manager.tear_down()
        self.workload_manager.tear_down()