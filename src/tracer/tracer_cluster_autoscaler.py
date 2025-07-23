"""
This class processes Kubernetes pod metrics and generates yaml of these objects for emulation.
It merges multiple sources of pod-related data, and outputs structured trace and setup files.
"""

import json
import pandas as pd
from util.k8s_object_generator import K8SObjectGenerator

class TracerClusterAutoscaler:
    """
    Processes Kubernetes pod and node metrics to generate structured trace and
    setup files suitable for KWOK emulation.

    This class ingests data from various CSV sources (pod resource requests,
    CPU usage, ownership details, status phases, replicaset ownership),
    performs several preprocessing and merging steps, and ultimately outputs
    JSON files. These files describe the initial setup (infrastructure and workload)
    and a time-series trace of events (object applications, deletions, scaling)
    for the emulation environment. It is specifically tailored to generate objects
    compatible with a KWOK-based simulation (e.g., not generating Karpenter-specific
    NodePools or Provisioners directly, as K8SObjectGenerator is called with karpenter=False).
    """

    def __init__(self, kube_pod_container_resource_requests_path, container_cpu_usage_seconds_total, kube_pod_owner_path, kube_pod_status_phase, kube_replicaset_owner_path, instance_types_path):
        """
        Initializes the Tracer class with the paths to various Kubernetes-related data files.
        """
        self.kube_pod_container_resource_requests_path = kube_pod_container_resource_requests_path
        self.container_cpu_usage_seconds_total_path = container_cpu_usage_seconds_total
        self.kube_pod_owner_path = kube_pod_owner_path
        self.kube_pod_status_phase_path = kube_pod_status_phase
        self.kube_replicaset_owner_path = kube_replicaset_owner_path
        self.instance_types_path = instance_types_path
        self.k8s_objects_generator = K8SObjectGenerator(karpenter=False, cluster_autoscaler=True)

    def log(self, message):
        """
        Logs a message with a "[TRACER]" prefix.
        """
        print(f"[TRACER] {message}")

    def load_data(self):
        """
        Load data from CSV files into pandas DataFrames.
        Logs an informational message before loading the data.
        """
        self.log("[INFO] Loading data from CSV files.")
        self.kube_pod_container_resource_requests = pd.read_csv(self.kube_pod_container_resource_requests_path)
        self.container_cpu_usage_seconds_total = pd.read_csv(self.container_cpu_usage_seconds_total_path)
        self.kube_pod_owner = pd.read_csv(self.kube_pod_owner_path)
        self.kube_pod_status_phase = pd.read_csv(self.kube_pod_status_phase_path)
        self.kube_replicaset_owner = pd.read_csv(self.kube_replicaset_owner_path)

    def normalize_timestamps(self, dfs_list):
        """
        Normalizes the timestamps in a list of DataFrames by aligning them to a fixed range of values.

        This method adjusts the "timestamp" column in each DataFrame by subtracting the minimum timestamp
        value from all timestamps in that DataFrame. It then filters the timestamps to retain only those
        that match a predefined list of fixed intervals (0 to 14400, with a step of 300 by default).
        """
        all_timestamps = dfs_list[0]['timestamp'].unique()
        all_timestamps.sort()
        min_timestamp = all_timestamps[0]
        max_timestamp = all_timestamps[-1]
        self.step = all_timestamps[1] - all_timestamps[0] if len(all_timestamps) > 1 else 0

        # Get normalized informations from all metrics
        min_timestamp_normalized = min_timestamp - min_timestamp
        max_timestamp_normalized = max_timestamp - min_timestamp
        timestamps = list(range(min_timestamp_normalized, max_timestamp_normalized + 1, self.step))

        # Normalize the timestamps of each DataFrame
        normalized_dfs = []
        for df in dfs_list:
            if "timestamp" in df.columns:
                min_timestamp = df["timestamp"].min()
                df = df.copy()
                df["timestamp"] = df["timestamp"] - min_timestamp
                # Filter to keep only the timestamps that are in the fixed list
                df = df[df["timestamp"].isin(timestamps)]
            normalized_dfs.append(df)
        return normalized_dfs

    def preprocess_dataframes(self):
        """
        Preprocesses multiple dataframes by normalizing their timestamps.

        This method logs the preprocessing step and applies the `normalize_timestamps` 
        function to all dataframes in the class. It ensures that all timestamps are aligned.

        The normalized dataframes are then reassigned to their respective attributes.
        """
        self.log("[INFO] Preprocessing dataframes.")
        self.kube_pod_container_resource_requests, \
        self.container_cpu_usage_seconds_total, \
        self.kube_pod_owner, \
        self.kube_pod_status_phase, \
        self.kube_replicaset_owner = self.normalize_timestamps([
            self.kube_pod_container_resource_requests,
            self.container_cpu_usage_seconds_total,
            self.kube_pod_owner,
            self.kube_pod_status_phase,
            self.kube_replicaset_owner
        ])

    def select_necessary_columns(self):
        """
        Selects and renames essential columns, and performs initial filtering
        on various DataFrames used in the trace generation.


        Operations performed:
        - On `self.container_cpu_usage_seconds_total`:
            - Selects 'timestamp', 'node_kubernetes_io_instance_type',
              'kubernetes_io_hostname', and 'pod'.
            - Renames 'node_kubernetes_io_instance_type' to 'instance_type'.
            - Renames 'kubernetes_io_hostname' to 'node'.
            - Removes duplicate rows based on 'pod' and 'timestamp', keeping
              the first occurrence.
        - On `self.kube_pod_container_resource_requests`:
            - Selects "timestamp", "pod", "namespace", "value", "resource",
              and "node".
        - On `self.kube_pod_owner`:
            - Removes duplicate rows based on 'pod', keeping the first occurrence.
            - Selects 'pod', 'owner_name', and 'owner_kind'.
        - On `self.kube_pod_status_phase`:
            - Filters out rows where the 'value' column (indicating phase activity) is 0.
            - Selects 'timestamp', 'pod', and 'phase'.
        - On `self.kube_replicaset_owner`:
            - Removes duplicate rows based on 'replicaset', keeping the first occurrence.
            - Selects 'replicaset', 'owner_kind', and 'owner_name'.
        """

        # Selecting only the desired final columns
        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total[['timestamp', 'node_kubernetes_io_instance_type', 'kubernetes_io_hostname', 'pod']]
        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total.rename(
            columns={
                'node_kubernetes_io_instance_type': 'instance_type',
                'kubernetes_io_hostname': 'node'
            }
        )
        self.container_cpu_usage_seconds_total = self.container_cpu_usage_seconds_total.drop_duplicates(subset=['pod', 'timestamp'], keep='first')

        self.kube_pod_container_resource_requests = self.kube_pod_container_resource_requests[["timestamp", "pod", "namespace", "value", "resource", "node"]]

        self.kube_pod_owner = self.kube_pod_owner.drop_duplicates(subset='pod', keep='first')
        self.kube_pod_owner = self.kube_pod_owner[['pod', 'owner_name', 'owner_kind']]

        self.kube_pod_status_phase = self.kube_pod_status_phase[self.kube_pod_status_phase['value'] != 0]
        self.kube_pod_status_phase = self.kube_pod_status_phase[['timestamp', 'pod', 'phase']]

        self.kube_replicaset_owner = self.kube_replicaset_owner.drop_duplicates(subset='replicaset', keep='first')
        self.kube_replicaset_owner = self.kube_replicaset_owner[['replicaset', 'owner_kind', 'owner_name']]

    def merge_container_usage_with_pods_phase(self):
        """
        Merges container CPU usage data with pod phase data.

        This method performs a left merge of `self.container_cpu_usage_seconds_total`
        (which contains CPU usage, node, and instance type information) with
        `self.kube_pod_status_phase` (containing pod phase information) using
        'timestamp' and 'pod' as merge keys.
        Any resulting rows with missing 'phase' values are filled with 'Pending'.
        The final merged DataFrame is stored in `self.karpenter_pods_state`.
        """

        self.karpenter_pods_state = pd.merge(
            self.container_cpu_usage_seconds_total,
            self.kube_pod_status_phase,
            on=["timestamp", "pod"],
            how="left"
        ).fillna({'phase': 'Pending'})

    def merge_pods_state_with_resources(self):
        """
        Merges pod state data with resource request data, processes the
        combined data, and generates a final DataFrame with aggregated and
        pivoted resource information (CPU and memory).

        Steps:
        1. Merges `self.kube_pod_container_resource_requests` (source of resource
           requests) with `self.karpenter_pods_state` (source of pod state,
           node, instance type, and phase) using 'timestamp' and 'pod' as keys
           (left join). Suffixes are used to distinguish columns from original
           DataFrames if names clash (e.g., 'node').
        2. The 'node' column in the merged DataFrame is populated using values
           from `node_karpenter_state` (from `self.karpenter_pods_state`),
           then original suffixed node columns are dropped.
        3. Missing values in 'node', 'instance_type' are filled with "unallocated".
           Missing 'phase' values are filled with "Pending".
        4. Forward-fill and backward-fill are applied to propagate known pod
           information across timestamps where it might be missing for that pod.
        5. Duplicate rows are dropped.
        6. Resource 'value's (CPU, memory) are summed up for each unique
           combination of 'timestamp', 'pod', 'namespace', 'instance_type',
           'node', and 'resource' type.
        7. The DataFrame is pivoted to transform 'resource' types (e.g., 'cpu',
           'memory') into distinct columns.
        8. Rows where either the 'cpu' or 'memory' column still has a placeholder
           'NA' (indicating missing data for that resource type) are filtered out.
        9. The processed DataFrame is stored in `self.df_final`.
        10. Logs the count of unique pods remaining in `self.df_final`.
        """
        
        # Direct merge using 'timestamp' and 'pod' as keys
        df_merged = pd.merge(
            self.kube_pod_container_resource_requests,
            self.karpenter_pods_state,
            on=["timestamp", "pod"],
            how="left",
            suffixes=('_resource_requests', '_karpenter_state')
        ).assign(
            node=lambda df: df["node_karpenter_state"]
        ).drop(
            columns=["node_resource_requests", "node_karpenter_state"]
        )

        df_merged["node"] = df_merged["node"].fillna("unallocated")
        df_merged["instance_type"] = df_merged["instance_type"].fillna("unallocated")
        df_merged["phase"] = df_merged["phase"].fillna("Pending")

        # Filling the dataframe with the closest occurrence of this pod where there are NA values
        df_merged = df_merged.ffill().bfill()

        # Remove duplicate rows, keeping only unique ones
        df_merged = df_merged.drop_duplicates()

        # Sum all occurrences of CPU and memory for each timestamp of a pod
        df_merged = df_merged.groupby(['timestamp', 'pod', 'namespace', 'instance_type', 'node', 'resource']).agg({
            'value': 'sum'
        }).reset_index()

        # Use pivot to transform 'resource' into separate columns for 'cpu' and 'memory'
        df_pivoted = df_merged.pivot(index=['timestamp', 'pod', 'namespace', 'instance_type', 'node'],
                            columns='resource',
                            values='value').reset_index()

        # Fill missing values with 'NA' for CPU and memory
        df_pivoted['cpu'] = df_pivoted['cpu'].fillna('NA')
        df_pivoted['memory'] = df_pivoted['memory'].fillna('NA')

        self.df_final = df_pivoted[~((df_pivoted['cpu'] == 'NA') | (df_pivoted['memory'] == 'NA'))]

        # Total count of unique pods created and removed
        total_pods = self.df_final['pod'].nunique()
        self.log(f"[INFO] Number of pods after remove NAs and pods that finish on first timestamp: {total_pods}")

    def merge_pods_resources_with_pod_owner(self):
        """
        Merges the main processed DataFrame (`self.df_final`) with pod
        ownership data (`self.kube_pod_owner`).

        This is a left join on the 'pod' column, enriching `self.df_final`
        with 'owner_name' and 'owner_kind' from `self.kube_pod_owner`.
        The 'owner_name' column (typically representing a ReplicaSet name
        at this stage) is then renamed to 'replicaset' in `self.df_final`
        for clarity in subsequent steps.
        """
        self.df_final = pd.merge(self.df_final, self.kube_pod_owner, on='pod', how='left')

        self.df_final.rename(columns={'owner_name': 'replicaset'}, inplace=True)

    def merge_pods_resources_with_replicaset_owner(self):
        """
        Merges the main processed DataFrame (`self.df_final`) with ReplicaSet
        ownership data (`self.kube_replicaset_owner`).

        This method performs a left join using the 'replicaset' column.
        It then intelligently combines 'owner_kind' and 'owner_name' fields
        that might exist with suffixes (e.g., 'owner_kind_x', 'owner_kind_y')
        from the merge, prioritizing data from `kube_replicaset_owner` (`_y` suffix)
        and then from `df_final` (`_x` suffix) if the former is missing.
        The 'replicaset' column (which at this point might be the replicaset's
        owner name, like a Deployment name) is also updated using `combine_first`
        from the 'owner_name' field that comes from `kube_replicaset_owner`.
        Redundant suffixed columns are then dropped.
        The result updates `self.df_final`.
        """
        df_merged = pd.merge(self.df_final, self.kube_replicaset_owner, on='replicaset', how='left')

        df_merged['owner_kind'] = df_merged['owner_kind_y'].combine_first(df_merged['owner_kind_x'])

        df_merged['replicaset'] = df_merged['owner_name'].combine_first(df_merged['replicaset'])

        self.df_final = df_merged.drop(columns=['owner_kind_x', 'owner_kind_y'])

    def remove_not_considered_resources_and_namespaces(self):
        """
        Removes rows from the dataframe `df_final` that belong to namespaces or resource kinds 
        that are not considered for further processing.
        """
        self.log("[INFO] Removing not considered resources and namespaces.")
        self.df_final = self.df_final[~self.df_final['namespace'].isin(['kube-system', 'monitoring'])]

        self.df_final = self.df_final[~self.df_final['owner_kind'].isin(['DaemonSet', 'Job'])]

    def process_and_save_pods_allocation(self):
        """
        Processes and saves pod allocation data.

        This method filters and processes pod allocation data from the `df_final` DataFrame,
        saving the results into two CSV files:
        1. A list of all unique nodes involved in the allocation.
        2. A detailed summary of pod allocations grouped by namespace, node, replicaset,
           owner kind, and instance type.
        """
        self.log("[INFO] Processing and saving pods allocation.")
        df_pods_allocation = self.df_final[self.df_final['timestamp'] == self.df_final['timestamp'].min()]

        df_pods_allocation = df_pods_allocation[~df_pods_allocation["node"].isin(["unallocated"]) & ~df_pods_allocation["instance_type"].isin(["unallocated"])]

        # Remove nodes that occur in just one timestamp
        node_counts = df_pods_allocation.groupby('node')['timestamp'].nunique()
        nodes_with_single_timestamp = node_counts[node_counts == 1].index.tolist()
        df_pods_allocation = df_pods_allocation[~df_pods_allocation['node'].isin(nodes_with_single_timestamp)]

        self.df_pods_allocation = df_pods_allocation.groupby(['namespace', 'node', 'replicaset', 'owner_kind', 'instance_type']).agg(
            pods_count=('replicaset', 'count'),
        ).reset_index()

        self.df_pods_allocation.to_csv("/tmp/pods_allocation.csv", index=False)

    def process_and_save_final_trace(self):
        """
        Processes and saves the final trace data by aggregating and transforming the dataframe.
        The resulting CSV file contains the final trace data with the following columns:
        - 'timestamp', 'namespace', 'replicaset', 'owner_kind', 'pods', 'cpu', 'memory', and 'action'.
        """
        self.log("[INFO] Processing and saving final trace.")
        df_adjusted = self.df_final.groupby(['timestamp', 'namespace', 'replicaset', 'owner_kind']).agg(
            pods_count=('replicaset', 'count'),
            cpu_count=('cpu', 'mean'),
            memory_count=('memory', 'mean')
        ).reset_index()

        df_adjusted = df_adjusted.rename(columns={'pods_count': 'pods', 'cpu_count': 'cpu', 'memory_count': 'memory'})

        # This step is to add the action related to the replicaset
        df_adjusted['action'] = 'scale'

        first_occurrences = df_adjusted.groupby(['replicaset','namespace']).head(1).index
        df_adjusted.loc[first_occurrences, 'action'] = 'create'

        last_occurrences = df_adjusted.groupby(['replicaset','namespace']).tail(1).index
        df_adjusted.loc[last_occurrences, 'action'] = 'delete'

        df_adjusted['pods_changed'] = df_adjusted.groupby('replicaset')['pods'].diff().fillna(1) != 0

        self.df_final = df_adjusted[df_adjusted['pods_changed'] | (df_adjusted['action'].isin(['create', 'delete']))].drop(columns=['pods_changed'])

    def generate_workload_objects(self):
        """
        Generates structured workload objects for setup and emulation phases.

        This method iterates through `self.df_final` grouped by 'timestamp'.
        - For the very first timestamp, it generates initial deployment objects
          which are considered as 'setup' data.
        - For all subsequent timestamps, it generates applied objects (new
          deployments), deleted objects (names of deployments to remove), and
          scaled replicasets based on the trace data for that timestamp.
          These are added to the 'emulation' list.

        It utilizes `self.k8s_objects_generator.generate_deployments()` to
        create the Kubernetes object representations.

        Returns:
            dict: A dictionary structured for emulation, containing:
                - 'setup' (dict): Deployment objects for the initial setup phase,
                  as returned by the K8SObjectGenerator for the first timestamp.
                - 'emulation' (list): A list of dictionaries, each representing
                  a time-stepped entry in the emulation trace. Each entry includes:
                    - "timestamp" (int): The normalized timestamp of the event.
                    - "applied_objects" (list): Kubernetes objects (e.g., Deployments)
                      to be applied at this timestamp.
                    - "deleted_objects" (list): Names of objects to be deleted.
                    - "scaled_replicasets" (list): Information about replicasets
                      that need scaling.
        """
        workload_objects = {'setup': {}, 'emulation': []}

        first_timestamp = self.df_final['timestamp'].min()

        for timestamp, group in self.df_final.groupby('timestamp'):
            if timestamp == first_timestamp:
                workload_objects['setup'], _, _ = self.k8s_objects_generator.generate_deployments(group)
            else:
                applied_objects, deleted_objects, scaled_replicasets = self.k8s_objects_generator.generate_deployments(group)
                workload_objects['emulation'].append({
                    "timestamp": int(timestamp),
                    "applied_objects": applied_objects,
                    "deleted_objects": deleted_objects,
                    "scaled_replicasets": scaled_replicasets
                })

        return workload_objects
    
    def process_and_save_infrastructure_objects(self):
        """
        Processes `self.df_final` to identify and mark node creation and
        deletion events based on their first and last appearance with a specific
        instance type. The result is stored in `self.df_infrastructure`.

        Steps:
        1. Copies `self.df_final` to `self.df_infrastructure`.
        2. Selects unique combinations of 'timestamp', 'node', and 'instance_type'.
        3. Sorts by 'node', 'instance_type', and 'timestamp'.
        4. For each ('node', 'instance_type') pair, marks the first timestamped
           occurrence as a 'create' action and the last as a 'delete' action.
        5. Filters to keep only these 'create' and 'delete' action rows.
        6. Further filters to retain only ('node', 'instance_type') pairs that
           have more than one action (i.e., both a create and a delete, implying
           the node existed for some duration).
        7. Removes entries where 'node' or 'instance_type' is "unallocated".
        8. The final DataFrame, sorted by timestamp, action, instance_type,
           and node, is stored in `self.df_infrastructure`.
        An informational message is logged before processing.
        """
        self.log("[INFO] Processing and saving infrastructure objects.")

        # Saving the final_trace to obtain the infrastructure objects
        self.df_infrastructure = self.df_final.copy()

        # Marcar a primeira e a última ocorrência de cada nó (com instance_type), independente do timestamp
        infra = self.df_infrastructure[['timestamp', 'node', 'instance_type']].drop_duplicates()

        # Para cada node/instance_type, marcar a primeira e última ocorrência
        infra = infra.sort_values(['node', 'instance_type', 'timestamp'])
        first_idx = infra.groupby(['node', 'instance_type']).head(1).index
        last_idx = infra.groupby(['node', 'instance_type']).tail(1).index

        infra['action'] = ''
        infra.loc[first_idx, 'action'] = 'create'
        infra.loc[last_idx, 'action'] = 'delete'

        # Manter apenas os eventos 'create' e 'delete'
        infra = infra[infra['action'].isin(['create', 'delete'])]

        # Remover nodes com valores faltantes ou que só aparecem uma vez
        counts = infra.groupby(['node', 'instance_type'])['action'].count()
        valid_nodes = counts[counts > 1].index
        infra = infra.set_index(['node', 'instance_type']).loc[valid_nodes].reset_index()

        infra = infra[(infra['node'] != 'unallocated') & (infra['instance_type'] != 'unallocated')]

        self.df_infrastructure = infra.sort_values(['timestamp', 'action', 'instance_type', 'node'])

    def generate_infrastructure_objects(self):
        """
        Generates structured data for infrastructure (Node) object lifecycle events.

        This method processes `self.df_infrastructure`, which contains 'create'
        and 'delete' actions for nodes at specific timestamps. It loads instance
        type definitions from `self.instance_types_path` to generate full
        Kubernetes Node object specifications using `self.k8s_objects_generator.generate_node()`.

        The output dictionary separates initial node setup from subsequent
        emulation events (node additions/removals).

        Returns:
            dict: A dictionary with two keys:
                - 'setup' (list): A list of full Node objects that are marked
                  for creation at the very first timestamp in `self.df_infrastructure`.
                - 'emulation' (list): A list of dictionaries, one for each
                  timestamp present in `self.df_infrastructure`. Each dictionary includes:
                    - "timestamp" (int): The normalized timestamp of the event.
                    - "applied_objects" (list): Full Node objects to be created at
                      this timestamp (this list is empty if the current timestamp
                      is the first one, as those nodes go into the 'setup' list).
                    - "deleted_objects" (list): Names (strings) of Node objects
                      to be deleted at this timestamp.
        """
        infrastructure_objects = {'setup': [], 'emulation': []}

        return infrastructure_objects

    def process_and_save_workload_and_infrastructure_objects(self):
        """
        Processes and saves the output objects generated by the trace emulation.
        """
        self.log("[INFO] Processing and saving output objects.")
        workload_objects = self.generate_workload_objects()
        infrastructure_objects = self.generate_infrastructure_objects()

        workload_objects_json = json.dumps(workload_objects, indent=4)
        infrastructure_objects_json = json.dumps(infrastructure_objects, indent=4)

        with open('/tmp/workload_description.json', 'w', encoding="utf-8") as f:
            f.write(workload_objects_json)

        with open('/tmp/infrastructure_description.json', 'w', encoding="utf-8") as f:
            f.write(infrastructure_objects_json)

    def run(self):
        """
        Executes the main workflow of the Tracer class.

        This method orchestrates the entire tracing process by calling the appropriate
        helper methods in the correct sequence.
        """
        self.log("[INFO] Starting Tracer.")
        self.load_data()
        self.preprocess_dataframes()
        self.select_necessary_columns()
        self.merge_container_usage_with_pods_phase()
        self.merge_pods_state_with_resources()
        self.merge_pods_resources_with_pod_owner()
        self.merge_pods_resources_with_replicaset_owner()
        self.remove_not_considered_resources_and_namespaces()
        self.process_and_save_pods_allocation()
        self.process_and_save_infrastructure_objects()
        self.process_and_save_final_trace()
        self.process_and_save_workload_and_infrastructure_objects()