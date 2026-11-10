from decimal import Decimal
from unittest.mock import Mock

import pytest
from kubernetes.utils.quantity import parse_quantity

from util.k8s_objects.cluster_resource_usage_generator import ClusterResourceUsageGenerator
from workload.usage.usage_manager import UsageManager


def test_generator_uses_static_quantities_for_one_pod():
    body = ClusterResourceUsageGenerator().generate_cluster_resource_usage(
        cru_name="usage-app-pod-1",
        namespace="app",
        pod_name="pod-1",
        container="web",
        cpu="23457u",
        memory="134217728",
    )

    assert body == {
        "apiVersion": "kwok.x-k8s.io/v1alpha1",
        "kind": "ClusterResourceUsage",
        "metadata": {"name": "usage-app-pod-1"},
        "spec": {
            "selector": {"matchNamespaces": ["app"], "matchNames": ["pod-1"]},
            "usages": [{
                "containers": ["web"],
                "usage": {
                    "cpu": {"value": "23457u"},
                    "memory": {"value": "134217728"},
                },
            }],
        },
    }


@pytest.fixture
def manager():
    manager = UsageManager(Mock())
    manager.cru_generator = ClusterResourceUsageGenerator()
    manager.k8s_api = Mock()
    return manager


@pytest.mark.parametrize(
    "cpu,memory,expected_cpu,expected_memory",
    [
        (0, 0, "0u", "0"),
        (0.0234567, 134217728, "23457u", "134217728"),
        (0.000001, 1, "1u", "1"),
        (0.0000004, 0.4, "0u", "0"),
        (1.2345678, 1024.6, "1234568u", "1025"),
        (0.0000025, 1024.5, "2u", "1024"),
    ],
)
def test_assignment_formats_kubernetes_quantities(
    manager, cpu, memory, expected_cpu, expected_memory
):
    manager.apply_assignment(
        ("app", "web"), {("app", "pod-1"): {"cpu": cpu, "memory": memory}}
    )

    body = manager.k8s_api.create_infrastructure_object.call_args.kwargs["body"]
    usage = body["spec"]["usages"][0]["usage"]
    assert usage == {
        "cpu": {"value": expected_cpu},
        "memory": {"value": expected_memory},
    }
    assert parse_quantity(usage["cpu"]["value"]) == (
        Decimal(expected_cpu[:-1]) / 1_000_000
    )
    assert parse_quantity(usage["memory"]["value"]) == Decimal(expected_memory)


def test_changing_usage_patches_same_cru_with_static_values(manager):
    workload_key = ("app", "web")
    for index in range(1, 101):
        manager.apply_assignment(workload_key, {
            ("app", "pod-1"): {"cpu": index / 1_000_000, "memory": index},
        })

    manager.k8s_api.create_infrastructure_object.assert_called_once()
    patches = manager.k8s_api.patch_cluster_custom_object.call_args_list
    assert len(patches) == 99
    for index, patch in enumerate(patches, start=2):
        assert patch.kwargs["name"] == "usage-app-pod-1"
        assert patch.kwargs["body"]["spec"]["usages"] == [{
            "containers": ["web"],
            "usage": {
                "cpu": {"value": f"{index}u"},
                "memory": {"value": str(index)},
            },
        }]
    assert manager.existing_crus == {"usage-app-pod-1"}
    assert manager.managed_crus_by_workload[workload_key] == {"usage-app-pod-1"}
    manager.k8s_api.delete_cluster_custom_object.assert_not_called()
