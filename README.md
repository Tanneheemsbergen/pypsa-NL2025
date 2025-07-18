![Python ≥3.8](https://img.shields.io/badge/python-%3E%3D3.8-blue) ![License: MIT](https://img.shields.io/badge/license-MIT-green) [![Documentation](https://readthedocs.org/projects/pypsa-eur/badge/?version=latest)](https://pypsa-eur.readthedocs.io/en/latest/)  ![Repo size](https://img.shields.io/github/repo-size/Tanneheemsbergen/pypsa-NL2025) [![Chat on Discord](https://img.shields.io/discord/911692131440148490?label=Chat%20on%20Discord)](https://discord.com/channels/911692131440148490/911728377193451550)

# PyPSA NL2025: Dutch R-BESS Energy System Modeling for 2025
An enhanced PyPSA framework tailored to evaluate the optimal deployment of residential battery energy storage systems (R-BESS) in the distribution network for the year 2025. This repository provides tools to:

- Simulate multiple market scenarios (day‑ahead, imbalance‑only, value stacking)  
- Run both annual and weekly rolling‑horizon optimizations  
- Analyze network congestion and battery economics  
- Export results and visualizations for reporting and decision support  

Such analysis is vital for understanding how strategic storage placement can enhance grid stability, integrate renewables, and inform long‑term energy planning.

## Table of Contents
- [Project Description](#project-description)
- [Disclaimer & Limitations](#disclaimer-limitations)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Project Description

PyPSA NL2025 is a Python-based framework built on top of [PyPSA](https://pypsa.org/) for modeling and optimizing the electricity distribution network in Monnickendam, Netherlands. It supports multiple market scenarios (day‑ahead, imbalance‑only, value stacking) and offers both annual and weekly rolling‑horizon simulations with detailed analysis of congestion and battery economics.

<a name="disclaimer-limitations"></a>
## Disclaimer & Limitations

> **Please note:** PyPSA NL2025 builds on the core PyPSA framework and is therefore subject to all its inherent limitations and assumptions. Before using this toolkit for critical planning or research, review the following resources:

- **PyPSA Limitations:**  
  *Numerical solvers, model granularity, and data quality can affect results.*  
  See the official limitations discussion for details:  
  https://pypsa-eur.readthedocs.io/en/latest/limitations.html

- **Data**  
  All data is provided except from the substation data. These loadlevels (per 15 min) should be retrieved from the distribution system operator. 

- **PyPSA Documentation:**  
  *Full user guide, tutorials, and API reference.*  
  https://pypsa-eur.readthedocs.io/en/latest/

- **PyPSA Core Paper:**  
  *Nick Kelly et al., “PyPSA: Python for Power System Analysis,”*  
  arXiv:1806.01613 → https://arxiv.org/abs/1806.01613

By using this software, you acknowledge these limitations and agree to validate results against high‑fidelity models or empirical data where necessary.  

## Features

- **Scenario‑based simulations**: Imbalance‑only, DAM‑only, value stacking, time‑constrained dispatch.  
- **Rolling‑horizon optimization**: Weekly and annual time horizons using PyPSA’s solver.  
- **Data pipelines**: Load and preprocess load profiles, day‑ahead and imbalance prices, solar generation.  
- **Modular architecture**: Core network builder, configuration loader, data loaders, and utilities.  
- **Analysis tools**: Congestion summaries, heatmaps, bus balance plots, battery profit calculations.  
- **Results export**: Automatic generation of CSVs and SVG plots for reporting.

## Installation

1. **Clone the repository**  
   ```bash
   git clone https://github.com/Tanneheemsbergen/pypsa-NL2025.git
   cd pypsa-NL2025
   ```

2. **Set up the environment**  
   It is recommended to use 'mamba' or `conda`:
   ```bash
   conda env create -f environment.yaml
   conda activate pypsa-nl2025
   ```
   If `environment.yaml` is incomplete or not present, install dependencies manually:
   ```bash
   pip install pandas numpy pyyaml pypsa vresutils cdsapi powerplantmatching tsam matplotlib
   ```

3. **Prepare input data**  
   ```bash
   # Place your CSV files in the data directory
   ls data/
   # Or update the paths in config/defaults.yaml
   ```

## Usage

### Annual Simulation
Run full‑year simulations for all scenarios defined in `scenarios/solve_scenarios.yaml`:
```bash
python solve_year.py
```
Edit the bottom of `solve_year.py` to change `year` and `scenario_to_run` as needed.

### Weekly Simulation
Simulate a single week:
```bash
python solve_week.py
```
Modify `year`, `week`, and `scenario_to_run` in `solve_week.py` to customize.

### Extended Scenario Runner
Use `solve2_year.py` and `solve2_week.py` for grouped scenarios and advanced summary plots:
```bash
python solve2_year.py
python solve2_week.py
```

## Architecture

```text
.
├── solve_year.py            # Annual simulation script
├── solve_week.py            # Weekly simulation script
├── solve2_year.py           # Extended annual runner
├── solve2_week.py           # Extended weekly runner
├── core/                    # Core modules (network builder, config loader, data loaders)
├── scenarios/               # Scenario definitions (YAML)
├── utils/                   # Utility functions (plots, analyses)
├── config/                  # Configuration files (defaults, battery specs)
├── data/                    # Input time‑series CSVs
├── plots/                   # Generated SVG plots
├── results/                 # Exported results (CSV, images)
└── tests/                   # Unit tests
```

## Configuration

- **`config/defaults.yaml`**: Paths for load, price, solar, and battery spec files.  
- **`config/battery_specs.yaml`**: Battery capacity, efficiency, and initial state parameters.  
- **`scenarios/`**: Define your simulation scenarios in `solve_scenarios.yaml` and `2solve_scenarios.yaml`.

## API Reference

> *The `API/` folder can be used to retrieve weatherdata from Copernicus and market price data from ENTSO-E.*

## Contributing

We welcome contributions! Please fork the repo, create a feature branch, and submit a pull request.

- Follow [PEP8](https://www.python.org/dev/peps/pep-0008/) coding standards.  
- Add tests under `tests/` and ensure they pass with:
  ```bash
  pytest tests/
  ```

## License

This project is licensed under the [MIT License](LICENSE). *Please add a LICENSE file to this repository if missing.*

## Contact

For questions or support, open an issue on GitHub or reach out to the maintainer [@Tanneheemsbergen](https://github.com/Tanneheemsbergen).
