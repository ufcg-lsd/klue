import pandas as pd

def reduce_csv_max_entries(input_csv, output_csv, max_entries_per_timestamp=5):
    df = pd.read_csv(input_csv)

    result = df.groupby('timestamp').head(max_entries_per_timestamp).reset_index(drop=True)

    result.to_csv(output_csv, index=False)

input_csv_path = 'artificial_kube_replicaset_owner.csv'

reduce_csv_max_entries(input_csv_path, input_csv_path)

