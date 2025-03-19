import pandas as pd

def check_csv_sorted_by_timestamp(csv_path):
    # Ler o arquivo CSV
    df = pd.read_csv(csv_path)

    # Checar se a coluna 'timestamp' está ordenada
    if df['timestamp'].is_monotonic_increasing:
        print("O arquivo está ordenado por timestamp.")
        return True
    else:
        print("O arquivo NÃO está ordenado por timestamp.")
        return False

csv_path = 'artificial_kube_pod_owner.csv'

check_csv_sorted_by_timestamp(csv_path)

