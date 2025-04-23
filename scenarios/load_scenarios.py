import os
import yaml

def load_scenarios(path="scenarios/solve_scenarios.yaml"):
    """
    Load simulation scenarios from the specified YAML file.
    Returns a list of scenario dictionaries.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Scenario file not found at: {path}")

    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not config or "scenarios" not in config:
        raise ValueError("Scenarios missing or malformed in YAML file.")

    return config["scenarios"]

def load_scenarios2(path="scenarios/2solve_scenarios.yaml"):
    """
    Load simulation scenarios from the secondary scenario file.
    Returns a list of scenario dictionaries.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Scenario file not found at: {path}")

    with open(path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not config or "scenarios" not in config:
        raise ValueError("Scenarios missing or malformed in YAML file.")

    return config["scenarios"]
