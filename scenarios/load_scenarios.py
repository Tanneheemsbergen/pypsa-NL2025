import os
import yaml

def load_scenarios(yaml_file=None):
    if yaml_file is None:
        yaml_file = os.path.join(os.path.dirname(__file__), "scenarios.yaml")
    with open(yaml_file, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    if config is None:
        raise ValueError(f"The YAML file '{yaml_file}' is empty or malformed.")
    return config.get("scenarios", [])
