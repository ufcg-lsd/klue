import csv
import requests
import time
import json
import os
from datetime import datetime, timedelta
import zipfile
import glob

class Collector:
    def __init__(self, step, metrics_file='metrics.txt', prometheus_host="http://localhost:30222"):
        self.prometheus_host = prometheus_host
        self.step = int(step)
        self.metrics_file = metrics_file

    def log(self, message):
        print(f"[COLLECTOR] {message}")

    def read_metrics(self):
        with open(self.metrics_file, 'r') as f:
            metrics = [line.strip() for line in f]
        return metrics

    def request_metrics(self, metric):
        end_time = int(time.time())  # Current time as end
        start_time = end_time - int(self.duration.total_seconds())  # Start time based on duration

        if not self.step or self.step <= 0:
            self.log(f"[ERROR] Invalid step value: {self.step}. It must be a positive integer.")
            return None

        try:
            step_duration = f"{self.step}s"
            response = requests.get(
                f"{self.prometheus_host}/api/v1/query_range",
                params={
                    "query": metric,
                    "start": start_time,
                    "end": end_time,
                    "step": step_duration
                }
            )

            if response.status_code != 200:
                self.log(f"[ERROR] Failed to fetch metric {metric}: {response.text}")
                return None

            return response
        except requests.RequestException as e:
            self.log(f"[ERROR] Request exception for metric {metric}: {e}")
            return None

    def write_csv(self, output_dir):
        self.log(f"[INFO] Writing CSV files to {output_dir}")
        for metric in self.metrics:
            response = self.request_metrics(metric)

            if response is None:
                continue

            try:
                results = response.json().get("data", {}).get("result", [])
            except json.JSONDecodeError:
                self.log(f"[ERROR] Failed to decode JSON for metric {metric}")
                continue

            if len(results) == 0:
                self.log(f"[INFO] No results for metric {metric}")
                continue

            metric_name = results[0]["metric"].get("__name__", "")

            with open(f"{output_dir}/{metric_name}.csv", "w") as f:
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

    def collect(self, duration):
        self.log(f"[INFO] Collecting metrics of this emulation for {duration} seconds.")
        self.duration = timedelta(seconds=int(duration))
        self.metrics = self.read_metrics()
        now = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

        output_dir = f"output_csv_{now}"
        os.makedirs(output_dir, exist_ok=True)
        self.write_csv(output_dir)

        # Zip the CSV files
        with zipfile.ZipFile(f"{output_dir}.zip", "w") as zip:
            for file in glob.glob(f"{output_dir}/*.csv"):
                zip.write(file)

        self.log(f"[INFO] CSV files zipped to {output_dir}.zip")
