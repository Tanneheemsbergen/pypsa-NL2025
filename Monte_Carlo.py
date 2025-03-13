import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

def load_and_simulate_weather(file_path, num_simulations=1000):
    """
    Loads solar irradiation data, fits a probability distribution, 
    performs Monte Carlo simulation, and returns synthetic datasets.
    """
    # Load dataset
    df = pd.read_csv(file_path)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Fit Normal Distribution to Electricity Data
    mu, sigma = norm.fit(df['electricity'])
    
    # Generate Monte Carlo Simulations
    simulations = np.random.normal(mu, sigma, size=(len(df), num_simulations))
    
    # Ensure No Negative Values (Solar irradiation cannot be negative)
    simulations = np.maximum(simulations, 0)
    
    # Convert to DataFrame
    mc_df = pd.DataFrame(simulations, index=df.index, 
                          columns=[f'Scenario_{i+1}' for i in range(num_simulations)])
    
    # Save the synthetic dataset in the same directory as the input file
    output_path = file_path.replace("cleaned_solar_data.csv", "simulated_solar_data.csv")
    mc_df.to_csv(output_path)
    
    # Visualization of Monte Carlo distribution
    plt.figure(figsize=(10, 6))
    plt.hist(mc_df.iloc[:, :100].values.flatten(), bins=100, density=True, alpha=0.6, color='b')
    xmin, xmax = plt.xlim()
    x = np.linspace(xmin, xmax, 100)
    p = norm.pdf(x, mu, sigma)
    plt.plot(x, p, 'k', linewidth=2)
    plt.title("Monte Carlo Simulated Distribution of Solar Irradiation")
    plt.xlabel("Solar Irradiation (kW)")
    plt.ylabel("Density")
    plt.show()
    
    return mc_df

# Example Usage
file_path = "data/cleaned_solar_data.csv"  # Adjust to your actual file path
simulated_data = load_and_simulate_weather(file_path)

# Display first few rows of synthetic dataset
simulated_data.head()
