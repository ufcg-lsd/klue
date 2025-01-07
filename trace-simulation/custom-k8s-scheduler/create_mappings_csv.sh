#!/bin/bash

# Filename for the CSV output
output_file="pod_node_mapping.csv"

# Add CSV header
echo "Pod,Node" > "$output_file"

# Loop through each namespace provided as an argument
for namespace in "$@"
do
  # Get pod and node information from the current namespace
  kubectl get pods -n "$namespace" --no-headers -o custom-columns="POD:.metadata.name,NODE:.spec.nodeName" >> "$output_file"
done

echo "CSV file created with pod-node mappings."

