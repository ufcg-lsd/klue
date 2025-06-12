import pytest
from main import Main
from manager import Manager
from infrastructure.manager import InfrastructureManager
from workload.manager import WorkloadManager
from collector import Collector
from pathlib import Path
import subprocess
import os

ROOT_DIRECTORY = Path('.').resolve()
MOCK_PATH = f'{ROOT_DIRECTORY}/tests/mock_data/'

@pytest.fixture(autouse=True)
def setup_and_teardown_cluster():
    # Delete the minikube cluster before the test
    subprocess.run(["bash", "delete-cluster.sh"], input="2\n", text=True, check=True)
    # Remove temporary CSV and JSON files if it exists
    os.system("rm -f /tmp/*.csv /tmp/*.json")
    # Create the minikube cluster before the test
    subprocess.run(["bash", "create-cluster.sh"], input="2\n", text=True, check=True)
    # Run emulation with the flags --dev --use-karpenter before the test
    subprocess.run(["bash", "execute-emulation.sh", "--dev", "--use-karpenter"], check=True)

    yield
    # Delete the minikube cluster after the test
    subprocess.run(["bash", "delete-cluster.sh"], input="2\n", text=True, check=True)

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_karpenter_dynamic_infra_dynamic_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="dynamic",
        workload="dynamic"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_karpenter_static_infra_dynamic_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="static",
        workload="dynamic"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_karpenter_dynamic_infra_static_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="dynamic",
        workload="static"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_karpenter_static_infra_static_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="static",
        workload="static"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_no_karpenter_dynamic_infra_dynamic_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="dynamic",
        workload="dynamic"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_no_karpenter_static_infra_dynamic_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="static",
        workload="dynamic"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_no_karpenter_dynamic_infra_static_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="dynamic",
        workload="static"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1

# After 5 minutes, the test will fail if it is not completed
@pytest.mark.timeout(300)
def test_workflow_no_karpenter_static_infra_static_workload(mocker):
    # Spy on the run method of the Manager class
    spy_run = mocker.spy(Manager, "run")

    # Spy on methods directly in the Manager classes
    spy_infra_before_setup = mocker.spy(InfrastructureManager, "before_setup")
    spy_infra_setup = mocker.spy(InfrastructureManager, "setup")
    spy_infra_before_emulation = mocker.spy(InfrastructureManager, "before_emulation")
    spy_infra_emulation = mocker.spy(InfrastructureManager, "emulation")
    spy_infra_tear_down = mocker.spy(InfrastructureManager, "tear_down")
    spy_expand_nodepools_disruption_time = mocker.spy(InfrastructureManager, "expand_nodepools_disruption_time")
    spy_restore_nodepools_disruption_time = mocker.spy(InfrastructureManager, "restore_nodepools_disruption_time")
    spy_count_nodes_in_input_data = mocker.spy(InfrastructureManager, "count_nodes_in_input_data")

    spy_workload_before_setup = mocker.spy(WorkloadManager, "before_setup")
    spy_workload_setup = mocker.spy(WorkloadManager, "setup")
    spy_workload_before_emulation = mocker.spy(WorkloadManager, "before_emulation")
    spy_workload_emulation = mocker.spy(WorkloadManager, "emulation")
    spy_workload_tear_down = mocker.spy(WorkloadManager, "tear_down")
    spy_workload_wait_pods_ready = mocker.spy(WorkloadManager, "wait_pods_ready")
    spy_workload_namespace_exists = mocker.spy(WorkloadManager, "namespace_exists")
    spy_workload_create_namespace_if_not_exists = mocker.spy(WorkloadManager, "create_namespace_if_not_exists")
    spy_workload_count_pods_excluding_namespaces = mocker.spy(WorkloadManager, "count_pods_excluding_namespaces")

    # Spy on Collector methods
    spy_collector_collect = mocker.spy(Collector, "collect")

    main = Main(
        trace_path=f"{MOCK_PATH}",
        nodepool_path=f"{MOCK_PATH}nodepools.yaml",
        karpenter=True,
        tracer_skip=False,
        infrastructure="static",
        workload="static"
    )

    main.apply_nodepool()
    main.run_tracer()
    main.run_manager()

    # Check if Manager.run was called
    assert spy_run.call_count == 1

    # Check if InfrastructureManager methods were called
    assert spy_infra_before_setup.call_count == 1
    assert spy_infra_setup.call_count == 1
    assert spy_infra_before_emulation.call_count == 1
    assert spy_infra_emulation.call_count == 1
    assert spy_infra_tear_down.call_count == 1
    assert spy_expand_nodepools_disruption_time.call_count == 1
    assert spy_restore_nodepools_disruption_time.call_count == 1
    assert spy_count_nodes_in_input_data.call_count == 1

    # Check if WorkloadManager methods were called
    assert spy_workload_before_setup.call_count == 1
    assert spy_workload_setup.call_count == 1
    assert spy_workload_before_emulation.call_count == 1
    assert spy_workload_emulation.call_count == 1
    assert spy_workload_tear_down.call_count == 1
    assert spy_workload_wait_pods_ready.call_count == 1
    assert spy_workload_namespace_exists.call_count >= 1
    assert spy_workload_create_namespace_if_not_exists.call_count >= 1
    assert spy_workload_count_pods_excluding_namespaces.call_count >= 1

    # Check if Collector methods were
    assert spy_collector_collect.call_count >= 1