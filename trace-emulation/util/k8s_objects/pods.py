import pandas as pd

class PodsGenerator:
    def __init__(self):
        pass
    
    def put_cpu_unity(self, value):
        """
        Converte o valor de CPU para milicores (m) e retorna como string.
        """
        return f"{int(float(value) * 1000)}m"

    def put_memory_unity(self, value):
        """
        Converte o valor de memória de bytes para MiB e retorna como string.
        """
        mebibytes = int(value) // (2 ** 20)
        return f"{mebibytes}Mi"

    def get_pods_json(self, group: pd.DataFrame, node_toleration = False):
        '''
        Function to create a JSON that can be converted into a Pod YAML, for each line within a group of lines.
        The lines must follow this format:
        timestamp, pod, namespace, cpu, memory, action, instance_type, nodepool
        '''
        applied_objects, deleted_objects = {}, []
        for _, row in group.iterrows():
            tolerations = [
                {
                    "key": f"{row['nodepool']}",
                    "operator": "Exists",
                    "effect": "NoSchedule"
                }
            ]

            if node_toleration:
                tolerations.append(
                    {
                        "key": f"{row['node']}",
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }
                )
            namespace = row['namespace']
            pod_data = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": row['pod'], "namespace": namespace},
                "spec": {
                    "containers": [
                        {
                            "name": "fake-container",
                            "image": "fake"
                        }
                    ],
                    "tolerations": tolerations
                }
            }
            
            if row['cpu'] != 'NA' or row['memory'] != 'NA':
                pod_data["spec"]["containers"][0]["resources"] = {"requests": {}}
                if row['cpu'] != 'NA':
                    pod_data["spec"]["containers"][0]["resources"]["requests"]["cpu"] = self.put_cpu_unity(row['cpu'])
                if row['memory'] != 'NA':
                    pod_data["spec"]["containers"][0]["resources"]["requests"]["memory"] = self.put_memory_unity(row['memory'])
            
            if row['action'] == 'create':
                if namespace not in applied_objects:
                    applied_objects[namespace] = [pod_data]
                else:
                    applied_objects[namespace].append(pod_data)
            elif row['action'] == 'delete':
                deleted_objects.append({"name": row['pod'], "namespace": row['namespace']})
        return [applied_objects, deleted_objects]