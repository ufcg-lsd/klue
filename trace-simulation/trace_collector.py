import csv
import requests
import time
import json
import os
from datetime import datetime, timedelta
import zipfile
import glob

PROMETHEUS_HOST = "http://localhost:30222"
TIMESTAMP_FILE = "last_run_timestamp.txt"

def read_metrics():
    with open('metrics.txt', 'r') as f:
        metrics = [line.strip() for line in f]
    return metrics

def get_last_run_duration():
    if os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, 'r') as f:
            last_run_time = datetime.fromisoformat(f.read().strip())
        duration = datetime.now() - last_run_time
    else:
        duration = timedelta(hours=1)
    return duration

def update_last_run_timestamp():
    with open(TIMESTAMP_FILE, 'w') as f:
        f.write(datetime.now().isoformat())

def request_metrics(metric, duration):
    response = requests.get(
        f"{PROMETHEUS_HOST}/api/v1/query",
        params={"query": f"{metric}[{int(duration.total_seconds())}s]"}
    )
    return response

def write_csv(dir, metrics):
    duration = get_last_run_duration()
    update_last_run_timestamp()

    for metric in metrics:
        response = request_metrics(metric, duration)

        # Check if the response contains "data" and "result"
        try:
            results = response.json().get("data", {}).get("result", [])
        except json.JSONDecodeError:
            print(f"Failed to decode JSON for metric {metric}")
            continue

        if len(results) == 0:
            print(f"No results for metric {metric}")
            continue

        metric_name = results[0]["metric"].get("__name__", "")

        # Write the samples.
        with open(f"{dir}/{metric_name}.csv", "w") as f:
            writer = csv.writer(f)
            labelnames = list(results[0]["metric"].keys())

            writer.writerow(["name", "timestamp", "value"] + labelnames)

            for result in results:
                for values in result["values"]:
                    timestamp = values[0]
                    value = values[1]
                    row = [result["metric"].get("__name__", ""), timestamp, value]
                    for label in labelnames:
                        x = result["metric"].get(label, "")
                        row.append(x)
                    writer.writerow(row)


def write_json(f, metrics):
    results = []
    for metric in metrics:
        response = request_metrics(metric, timedelta(seconds=30))

        # Check if the response contains "data" and "result"
        try:
            metric_results = response.json().get("data", {}).get("result", [])
            if metric_results:
                results.append(metric_results)
            else:
                print(f"No results for metric {metric}")
        except json.JSONDecodeError:
            print(f"Failed to decode JSON for metric {metric}")
            continue

    json.dump(results, f, indent=4)

def main():
    while True:
        time.sleep(3600)
        metrics = read_metrics()
        now = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

        dir = f"output_csv_{now}"
        os.mkdir(dir)
        write_csv(dir, metrics)
        with zipfile.ZipFile(f"{dir}.zip", "w") as zip:
            for file in glob.glob(f"{dir}/*.csv"):
                zip.write(file)

if __name__ == "__main__":
    main()
