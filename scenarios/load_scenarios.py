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

def load_scenarios2(path="scenarios/2solve_scenarios.yaml") -> list[dict]:
    """
    Laadt een vlakke lijst van alle scenario's uit 2solve_scenarios.yaml,
    inclusief losse 'scenarios:' én groepen met 'scenario_groups:' + sub_scenarios.
    Elke sub_scenario krijgt nu ook een 'group' key.
    """
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    # 1) losse scenario's (key 'scenarios:')
    scenarios = data.get("scenarios", [])

    # 2) scenario-groepen (key 'scenario_groups:')
    for group in data.get("scenario_groups", []):
        # defaults uit de groep (excl. name en sub_scenarios)
        defaults = {
            k: v for k, v in group.items()
            if k not in ("name", "sub_scenarios")
        }
        for sub in group.get("sub_scenarios", []):
            merged = {
                "group": group["name"],   # ← ZO voegen we de groep toe
                "name": sub["name"],
                **defaults,
                **sub
            }
            scenarios.append(merged)

    return scenarios