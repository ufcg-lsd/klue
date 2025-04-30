"""
This class processes Kubernetes pod metrics and generates yaml of these objects for emulation.
It merges multiple sources of pod-related data, and outputs structured trace and setup files.
"""

import json
import pandas as pd
from util.k8s_object_generator import K8SObjectGenerator

class Tracer:
    """
    The Tracer class is responsible for processing Kubernetes pod and node data to generate
    a trace of resource allocation and usage over time. It integrates data from multiple
    sources, normalizes timestamps, preprocesses dataframes, and generates output files
    and objects for further analysis.

    Parameters:
        kube_pod_container_resource_requests_path (str): Path to the CSV file containing pod container resource requests.
        karpenter_pods_state_path (str): Path to the CSV file containing Karpenter pod state information.
        kube_pod_owner_path (str): Path to the CSV file containing pod owner information.
        kube_replicaset_owner_path (str): Path to the CSV file containing replicaset owner information.
    """

    def __init__(self, kube_pod_container_resource_requests_path, karpenter_pods_state_path, kube_pod_owner_path, kube_replicaset_owner_path):
        """
        Initializes the Tracer class with the paths to various Kubernetes-related data files.
        """
        self.kube_pod_container_resource_requests_path = kube_pod_container_resource_requests_path
        self.karpenter_pods_state_path = karpenter_pods_state_path
        self.kube_pod_owner_path = kube_pod_owner_path
        self.kube_replicaset_owner_path = kube_replicaset_owner_path
        self.k8s_objects_generator = K8SObjectGenerator()

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
        self.karpenter_pods_state = pd.read_csv(self.karpenter_pods_state_path)
        self.kube_pod_owner = pd.read_csv(self.kube_pod_owner_path)
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
        self.karpenter_pods_state, \
        self.kube_pod_owner, \
        self.kube_replicaset_owner = self.normalize_timestamps([
            self.kube_pod_container_resource_requests,
            self.karpenter_pods_state,
            self.kube_pod_owner,
            self.kube_replicaset_owner
        ])

    def select_necessary_columns(self):
        """
        Selects and processes the necessary columns from multiple DataFrame attributes.

        This method performs the following operations:
        1. Ensures the 'pod' column exists in `karpenter_pods_state` by copying data from the 'name.1' column if necessary.
        2. Filters `karpenter_pods_state` to retain only the specified columns: 
           ['timestamp', 'instance_type', 'node', 'pod', 'nodepool', 'phase'].
        3. Filters `kube_pod_container_resource_requests` to retain only the specified columns: 
           ['timestamp', 'pod', 'namespace', 'value', 'resource', 'node'].
        4. Removes duplicate rows in `kube_pod_owner` based on the 'pod' column, keeping the first occurrence, 
           and retains only the columns: ['pod', 'owner_name', 'owner_kind'].
        5. Removes duplicate rows in `kube_replicaset_owner` based on the 'replicaset' column, keeping the first occurrence, 
           and retains only the columns: ['replicaset', 'owner_kind', 'owner_name'].
        """
        if "pod" not in self.karpenter_pods_state.columns:
            self.karpenter_pods_state["pod"] = self.karpenter_pods_state["name.1"]

        # Selecting only the desired final columns
        self.karpenter_pods_state = self.karpenter_pods_state[['timestamp', 'instance_type', 'node', 'pod', 'nodepool', 'phase']]

        self.kube_pod_container_resource_requests = self.kube_pod_container_resource_requests[["timestamp", "pod", "namespace", "value", "resource", "node"]]

        self.kube_pod_owner = self.kube_pod_owner.drop_duplicates(subset='pod', keep='first')
        self.kube_pod_owner = self.kube_pod_owner[['pod', 'owner_name', 'owner_kind']]

        self.kube_replicaset_owner = self.kube_replicaset_owner.drop_duplicates(subset='replicaset', keep='first')
        self.kube_replicaset_owner = self.kube_replicaset_owner[['replicaset', 'owner_kind', 'owner_name']]

    def merge_pods_state_with_resources(self):
        """
        Merges Kubernetes pod state data with resource request data, processes the combined data,
        and generates a final DataFrame with aggregated and pivoted information.

        This method performs the following steps:
        1. Merges `self.kube_pod_container_resource_requests` and `self.karpenter_pods_state` DataFrames
           using `timestamp` and `pod` as keys, with a left join.
        2. Fills missing `node` values by prioritizing `node_karpenter_state` over `node_resource_requests`.
        3. Replaces missing values in `node`, `instance_type`, and `phase` columns with default values.
        4. Fills missing data for each pod using forward-fill and backward-fill methods.
        5. Removes duplicate rows from the merged DataFrame.
        6. Aggregates CPU and memory resource values for each unique combination of timestamp, pod, and other attributes.
        7. Pivots the `resource` column into separate `cpu` and `memory` columns.
        8. Filters out rows where either `cpu` or `memory` is missing (marked as 'NA').
        9. Logs the total number of unique pods remaining after filtering.
        """
        # Direct merge using 'timestamp' and 'pod' as keys
        df_merged = pd.merge(
            self.kube_pod_container_resource_requests,
            self.karpenter_pods_state,
            on=["timestamp", "pod"],
            how="left",
            suffixes=('_resource_requests', '_karpenter_state')
        ).assign(
            node=lambda df: df["node_karpenter_state"].fillna(df["node_resource_requests"])
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
        df_merged = df_merged.groupby(['timestamp', 'pod', 'namespace', 'nodepool', 'instance_type', 'node', 'resource']).agg({
            'value': 'sum'
        }).reset_index()

        # Use pivot to transform 'resource' into separate columns for 'cpu' and 'memory'
        df_pivoted = df_merged.pivot(index=['timestamp', 'pod', 'namespace', 'nodepool', 'instance_type', 'node'],
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
        Merges the DataFrame `df_final` with the `kube_pod_owner` DataFrame on the 'pod' column,
        using a left join. This operation associates each pod with its corresponding owner
        information. After the merge, the 'owner_name' column is renamed to 'replicaset'.

        This method is useful for enriching pod resource data with ownership details, such as
        identifying which ReplicaSet a pod belongs to.
        """
        self.df_final = pd.merge(self.df_final, self.kube_pod_owner, on='pod', how='left')

        self.df_final.rename(columns={'owner_name': 'replicaset'}, inplace=True)

    def merge_pods_resources_with_replicaset_owner(self):
        """
        Merges pod resource data with ReplicaSet owner information.

        This method performs a left join between the `df_final` DataFrame and the 
        `kube_replicaset_owner` DataFrame on the 'replicaset' column. It combines 
        the 'owner_kind' and 'replicaset' columns to ensure the resulting DataFrame 
        has the most complete and accurate information. The merged DataFrame is 
        then cleaned by dropping redundant columns and stored back in `df_final`.
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
        self.df_final = self.df_final[~self.df_final['namespace'].isin(['kube-system'])]

        self.df_final = self.df_final[~self.df_final['owner_kind'].isin(['DaemonSet', 'Job'])]

    def process_and_save_pods_allocation(self):
        """
        Processes and saves pod allocation data.

        This method filters and processes pod allocation data from the `df_final` DataFrame,
        saving the results into two CSV files:
        1. A list of all unique nodes involved in the allocation.
        2. A detailed summary of pod allocations grouped by namespace, node, nodepool, replicaset,
           owner kind, and instance type.
        """
        self.log("[INFO] Processing and saving pods allocation.")
        df_pods_allocation = self.df_final[self.df_final['timestamp'] == self.df_final['timestamp'].min()]

        df_pods_allocation = df_pods_allocation[~df_pods_allocation["node"].isin(["unallocated"]) & ~df_pods_allocation["instance_type"].isin(["unallocated"])]

        all_nodes = df_pods_allocation['node'].unique()

        all_nodes_df = pd.DataFrame(all_nodes, columns=["node"])

        all_nodes_df.to_csv("/tmp/all_nodes.csv", index=False)

        self.df_pods_allocation = df_pods_allocation.groupby(['namespace', 'node', 'nodepool', 'replicaset', 'owner_kind', 'instance_type']).agg(
            pods_count=('replicaset', 'count'),
        ).reset_index()

        self.df_pods_allocation.to_csv("/tmp/pods_allocation.csv", index=False)

    def process_and_save_final_trace(self):
        """
        Processes and saves the final trace data by aggregating and transforming the dataframe.
        The resulting CSV file contains the final trace data with the following columns:
        - 'timestamp', 'namespace', 'nodepool', 'replicaset', 'owner_kind', 'pods', 'cpu', 'memory', and 'action'.
        """
        self.log("[INFO] Processing and saving final trace.")
        df_adjusted = self.df_final.groupby(['timestamp', 'namespace', 'nodepool', 'replicaset', 'owner_kind']).agg(
            pods_count=('replicaset', 'count'),
            cpu_count=('cpu', 'mean'),
            memory_count=('memory', 'mean')
        ).reset_index()

        df_adjusted = df_adjusted.rename(columns={'pods_count': 'pods', 'cpu_count': 'cpu', 'memory_count': 'memory'})

        # This step is to add the action related to the replicaset
        df_adjusted['action'] = 'scale'

        first_occurrences = df_adjusted.groupby(['replicaset','nodepool','namespace']).head(1).index
        df_adjusted.loc[first_occurrences, 'action'] = 'create'

        last_occurrences = df_adjusted.groupby(['replicaset','nodepool','namespace']).tail(1).index
        df_adjusted.loc[last_occurrences, 'action'] = 'delete'

        df_adjusted['pods_changed'] = df_adjusted.groupby('replicaset')['pods'].diff().fillna(1) != 0

        self.df_final = df_adjusted[df_adjusted['pods_changed'] | (df_adjusted['action'].isin(['create', 'delete']))].drop(columns=['pods_changed'])

        self.df_final.to_csv('/tmp/final_trace.csv', index=False)

    def generate_trace_objects(self):
        """
        Generates trace objects based on the data in `self.df_final`.
        Returns:
            tuple: A tuple containing:
                - setup (dict): A dictionary with initial setup information, including:
                    - 'nodeclaims' (list): An empty list reserved for node claims.
                    - 'deployments' (list): A list of deployment objects generated for the first timestamp.
                - json_output (list): A list of dictionaries, each representing a trace entry for a 
                  specific timestamp. Each dictionary contains:
                    - "timestamp" (int): The timestamp of the event.
                    - "applied_objects" (list): A list of objects applied at this timestamp.
                    - "deleted_objects" (list): A list of objects deleted at this timestamp.
                    - "scaled_replicasets" (list): A list of scaled replica sets at this timestamp.
        """
        setup = {'nodeclaims': [], 'deployments': []}
        json_output = []

        first_timestamp = self.df_final['timestamp'].min()

        for timestamp, group in self.df_final.groupby('timestamp'):
            if timestamp == first_timestamp:
                setup['deployments'], _, _ = self.k8s_objects_generator.generate_deployments(group)
            else:
                applied_objects, deleted_objects, scaled_replicasets = self.k8s_objects_generator.generate_deployments(group)
                json_output.append({
                    "timestamp": int(timestamp),
                    "applied_objects": applied_objects,
                    "deleted_objects": deleted_objects,
                    "scaled_replicasets": scaled_replicasets
                })

        return setup, json_output

    def generate_nodeclaims(self):
        """
        Generates a list of node claims based on unique node and instance type combinations.

        This method processes pod allocation data to identify unique combinations of nodes,
        node pools, and instance types. It then generates node claims for each unique combination
        using the Kubernetes objects generator.
        """
        nodeclaims = []

        df_unique = self.df_pods_allocation.drop_duplicates(subset=['node', 'instance_type']).reset_index(drop=True)
        df_unique.to_csv("/tmp/nodeclaims.csv", index=False)

        df_grouped = df_unique.groupby(['node', 'nodepool', 'instance_type'])

        with open("data/instance_types.json", encoding="utf-8") as f:
            instance_data = json.load(f)

        for (_, nodepool_name, instance_type), _ in df_grouped:
            nodeclaim = self.k8s_objects_generator.generate_nodeclaim(instance_type, instance_data, nodepool_name)
            if nodeclaim:
                nodeclaims.append(nodeclaim)

        return nodeclaims

    def process_and_save_output_objects(self):
        """
        Processes and saves the output objects generated by the trace emulation.
        """
        self.log("[INFO] Processing and saving output objects.")
        setup, json_output = self.generate_trace_objects()
        setup['nodeclaims'] = self.generate_nodeclaims()

        final_json_output = {
            "setup": setup,
            "trace": json_output
        }

        json_result = json.dumps(final_json_output, indent=4)
        with open('/tmp/output_objects.json', 'w', encoding="utf-8") as f:
            f.write(json_result)

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
        self.merge_pods_state_with_resources()
        self.merge_pods_resources_with_pod_owner()
        self.merge_pods_resources_with_replicaset_owner()
        self.remove_not_considered_resources_and_namespaces()
        self.process_and_save_pods_allocation()
        self.process_and_save_final_trace()
        self.process_and_save_output_objects()

    def get_initial_input_step(self):
        """
        Returns the initial step size between unique, sorted timestamps in the dataframe.
        """
        return self.step
