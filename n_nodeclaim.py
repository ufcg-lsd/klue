import json
import time
import os
from datetime import datetime
from kubernetes import client
import subprocess
import pandas as pd

with open('/tmp/output_objects.json', 'r') as file:
    data = json.load(file)

def count_nodeclaims_in_setup(data):
    """ Count the number of nodeclaims in the setup part of the data. """
    setup = data.get('setup', {})
    nodeclaims = setup.get('nodeclaims', [])
    return len(nodeclaims)

# Assuming 'data' is already loaded from the JSON file as shown in your script
nodeclaims_count = count_nodeclaims_in_setup(data)
print(f"Number of Nodeclaims in Setup: {nodeclaims_count}")

