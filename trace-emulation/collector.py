import csv
import requests
import time
import json
import os
import sys
from datetime import datetime, timedelta
import zipfile
import glob

PROMETHEUS_HOST = "http://localhost:30222"
TIMESTAMP_FILE = "last_run_timestamp.txt"

def read_metrics():
    with open('metrics.txt', 'r') as f:
        metrics = [line.strip() for line in f]
    return metrics

def request_metrics(metric, duration, step):
    end_time = int(time.time())  # Current time as end
    start_time = end_time - int(duration.total_seconds())  # Start time based on duration

    # Ensure step is a valid duration
    if not step or step <= 0:
        print(f"Invalid step value: {step}. It must be a positive integer.")
        return None

    try:
        # Format step as a valid duration string, e.g., "30s"
        step_duration = f"{step}s"

        # Make the request to Prometheus
        response = requests.get(
            f"{PROMETHEUS_HOST}/api/v1/query_range",
            params={
                "query": metric,
                "start": start_time,
                "end": end_time,
                "step": step_duration
            }
        )

        # Check for request success
        if response.status_code != 200:
            print(f"Failed to fetch metric {metric}: {response.text}")
            return None

        return response
    except requests.RequestException as e:
        print(f"Error fetching metric {metric}: {e}")
        return None

def write_csv(dir, metrics, duration, step):
    for metric in metrics:
        response = request_metrics(metric, duration, step)

        # If the response is None, skip processing this metric
        if response is None:
            continue

        try:
            results = response.json().get("data", {}).get("result", [])
        except json.JSONDecodeError:
            print(f"Failed to decode JSON for metric {metric}")
            continue

        if len(results) == 0:
            print(f"No results for metric {metric}")
            continue

        metric_name = results[0]["metric"].get("__name__", "")

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

def main():
    if len(sys.argv) < 3:
        print("Usage: python script.py <duration_in_seconds> <step_in_seconds>")
        sys.exit(1)

    try:
        duration = timedelta(seconds=int(sys.argv[1]))
        step = int(sys.argv[2])
    except ValueError:
        print("Duration and step must be integers.")
        sys.exit(1)

    metrics = read_metrics()
    now = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

    dir = f"output_csv_{now}"
    os.makedirs(dir, exist_ok=True)
    write_csv(dir, metrics, duration, step)

    # Zip the CSV files
    with zipfile.ZipFile(f"{dir}.zip", "w") as zip:
        for file in glob.glob(f"{dir}/*.csv"):
            zip.write(file)

if __name__ == "__main__":
    main()

