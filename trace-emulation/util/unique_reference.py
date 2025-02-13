import random
import string
import uuid

class UniqueReferenceGenerator:
    def __init__(self, prefix="default", length=5):
        self.prefix = prefix
        self.length = length
        self.generated_names = set()
        self.generated_uuids = set()
    
    def generate_name(self):
        while True:
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=self.length))
            new_name = f"{self.prefix}-{suffix}"
            if new_name not in self.generated_names:
                self.generated_names.add(new_name)
                return new_name
            
    def generate_uuid(self):
        while True:
            new_uuid = str(uuid.uuid4())
            if new_uuid not in self.generated_uuids:
                self.generated_uuids.add(new_uuid)
                return new_uuid