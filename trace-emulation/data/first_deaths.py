import pandas as pd

df = pd.read_csv('karpenter_pods_state.csv')

first_timestamp = df['timestamp'].min()

first_timestamp_df = df[df['timestamp'] == first_timestamp]

first_timestamp_pods = set(first_timestamp_df['kubernetes_pod_instance'])

later_timestamps_df = df[df['timestamp'] != first_timestamp]

later_timestamp_pods = set(later_timestamps_df['kubernetes_pod_instance'])

unique_pods = first_timestamp_pods.difference(later_timestamp_pods)

print("Unique pods that only appear in the first timestamp:")
for pod in unique_pods:
    print(pod)

