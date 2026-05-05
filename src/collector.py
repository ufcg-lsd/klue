"""
Collector class is responsible for collecting metrics from a Prometheus server over a specified duration.
It reads metric names from a file, queries Prometheus for the metrics, and writes the results to CSV files.
The CSV files are then compressed into a zip archive for easier handling.
"""

import csv
import time
import json
import os
import zipfile
import glob
from datetime import datetime, timedelta
import requests

class Collector:
    """
    This class collect and process metrics from a Prometheus server.

    Attributes:
        prometheus_host (str): The base URL of the Prometheus server.
        step (int): The step interval (in seconds) for querying metrics.
        metrics_file (str): The file containing the list of metrics to collect.
    """
    def __init__(self, step, metrics_file='src/metrics.txt', prometheus_host="http://localhost:30222"):
        """
        Initializes the collector with the specified step interval, metrics file, 
        and Prometheus host URL.
        """
        self.prometheus_host = prometheus_host
        self.step = int(step)
        self.metrics_file = metrics_file

    def log(self, message):
        """
        Logs a message with a "[COLLECTOR]" prefix.
        """
        print(f"[COLLECTOR] {message}")

    def read_metrics(self):
        """
        Reads metrics from a specified file and returns them as a list of strings.

        The method opens the file specified by `self.metrics_file` in read mode,
        reads each line, strips any leading or trailing whitespace, and stores
        the cleaned lines in a list.
        """
        with open(self.metrics_file, 'r') as f:
            metrics = [line.strip() for line in f]
        return metrics

    def request_metrics(self, metric, start_time, end_time):
        """
        Fetches metrics from a Prometheus server within a specified time range.
        """

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

            return response.json()
        except requests.RequestException as e:
            self.log(f"[ERROR] Request exception for metric {metric}: {e}")
            return None

    def write_csv(self, output_dir, start_time, end_time):
        """
        Writes metrics data to CSV files in the specified output directory.

        This method iterates over a list of metrics, retrieves their data using
        the `request_metrics` method, and writes the results to individual CSV
        files. Each file is named after the metric's name and contains rows of
        timestamped values along with their associated labels.
        """
        self.log(f"[INFO] Writing CSV files to {output_dir}")
        for metric in self.metrics:
            data = self.request_metrics(metric, start_time, end_time)

            if data is None:
                continue

            try:
                results = data.get("data", {}).get("result", [])
            except json.JSONDecodeError:
                self.log(f"[ERROR] Failed to decode JSON for metric {metric}")
                continue

            if len(results) == 0:
                self.log(f"[INFO] No results for metric {metric}")
                continue

            metric_name = results[0]["metric"].get("__name__", "")

            file_path = f"{output_dir}/{metric_name}.csv"
            file_exists = os.path.isfile(file_path)

            with open(f"{output_dir}/{metric_name}.csv", "a", encoding="utf-8") as f:
                writer = csv.writer(f)
                
                # pega todas as labels possíveis (mais seguro)
                labelnames = sorted({
                    key
                    for result in results
                    for key in result["metric"].keys()
                })

                # escreve header só uma vez
                if not file_exists:
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

    def collect(self, start_time, end_time, output_dir):
        """
        Collects metrics for a specified duration, writes them to CSV files, 
        and compresses the files into a ZIP archive.

        Steps:
            1. Logs the start of the metric collection process.
            2. Reads the metrics and stores them.
            3. Creates a timestamped output directory for the CSV files.
            4. Writes the collected metrics to CSV files in the output directory.
            5. Compresses the CSV files into a ZIP archive.
            6. Logs the completion of the zipping process.
        """
        self.log(f"[INFO] Collecting metrics from {start_time} to {end_time}")
        self.metrics = self.read_metrics()

        os.makedirs(output_dir, exist_ok=True)
        self.write_csv(output_dir, start_time, end_time)

        # Zip the CSV files
        with zipfile.ZipFile(f"{output_dir}.zip", "w") as zip:
            for file in glob.glob(f"{output_dir}/*.csv"):
                zip.write(file)

        self.log(f"[INFO] CSV files zipped to {output_dir}.zip")
