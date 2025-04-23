import yaml
import os

def load_config(path="config/defaults.yaml"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as file:
        return yaml.safe_load(file)