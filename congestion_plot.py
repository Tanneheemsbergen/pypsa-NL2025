
# %%
import pandas as pd
import matplotlib.pyplot as plt
from network import create_network
import networkx as nx
import matplotlib.pyplot as plt

file_path = "data/SS_Monnickendam.csv"

# %%
"""Plots the load profile for SS Monnickendam and highlights capacity violations."""

# Load data
df = pd.read_csv(file_path, sep=';', decimal=',', parse_dates=['DATUM_TIJD'])
df.columns = df.columns.str.lower()
df = df[df["jaar"] == 2024].sort_values(by="datum_tijd")

# Calculate statistics
mean_load = df["belasting"].mean()
capacity_limit = 11.2 * 0.85 * 1000  # Convert MVA to kW

# Count the number of times the load exceeds the capacity
exceed_count = (df["belasting"] > capacity_limit).sum()
# Convert exceed_count to hours
exceed_hours = exceed_count * 15 / 60
print(f"Number of times load exceeds capacity: {exceed_count} (equivalent to {exceed_hours:.2f} hours)")

# Plot
plt.figure(figsize=(12,5))
plt.plot(df["datum_tijd"], df["belasting"], label="Load (BELASTING)", color='blue', linewidth=0.7)
plt.fill_between(df["datum_tijd"], df["belasting"], capacity_limit, where=df["belasting"] > capacity_limit, color='red', alpha=0.3, label="Over Capacity")
plt.axhline(y=capacity_limit, color='orange', linestyle='--', linewidth=1.5, label=f"Capacity Limit = {capacity_limit:.0f} kW")
plt.axhline(y=mean_load, color='green', linestyle='--', linewidth=1.5, label=f"Mean Load = {mean_load:.2f} kW")

plt.xlabel("Date")
plt.ylabel("Load (kW)")
plt.title("Load Profile for SS Monnickendam (2024)")
plt.legend()
plt.grid(True)
plt.show()

# %%
def plot_pypsa_network(network):
    """Plots the PyPSA network structure in a Jupyter Notebook."""
    
    # Create a directed graph
    G = nx.DiGraph()

    # Add buses as nodes
    for bus in network.buses.index:
        G.add_node(bus, color='lightblue', size=1000, label=bus)

    # Add loads as nodes
    for load in network.loads.index:
        G.add_node(load, color='lightgreen', size=800, label=load)

    # Add generators as nodes
    for generator in network.generators.index:
        G.add_node(generator, color='orange', size=900, label=generator)

    # Add stores (BESS) as nodes
    for store in network.stores.index:
        G.add_node(store, color='red', size=900, label=store)

    # Add links as edges
    for link in network.links.index:
        bus0 = network.links.at[link, "bus0"]
        bus1 = network.links.at[link, "bus1"]
        G.add_edge(bus0, bus1, label=link)

    # Extract node attributes
    node_colors = [G.nodes[n].get('color', 'gray') for n in G.nodes]
    node_sizes = [G.nodes[n].get('size', 500) for n in G.nodes]

    # Create the plot
    plt.figure(figsize=(12, 7))
    pos = nx.spring_layout(G, seed=42)  # Position nodes using a force-directed layout
    nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=node_sizes, edge_color='gray', font_size=10)
    
    # Draw edge labels
    edge_labels = {(u, v): d['label'] for u, v, d in G.edges(data=True)}
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    plt.title("PyPSA Network Structure")
    plt.show()
# %%
