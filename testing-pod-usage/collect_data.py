from src.collector import Collector

collector = Collector(step=15, prometheus_host="http://localhost:9090")
collector.collect(duration=120)