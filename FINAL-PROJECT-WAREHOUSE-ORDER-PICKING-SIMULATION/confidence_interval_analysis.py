import pandas as pd
import numpy as np
from scipy.stats import t

# Read the dataset from an Excel file
file_path = 'Warehouse_Metrics_Simulated_Data.xlsx'
sheet_name = 'Sheet1'  # Update this if your sheet name is different
data = pd.read_excel(file_path, sheet_name=sheet_name)

# Identify KPI columns based on numeric data type
kpi_columns = data.select_dtypes(include=[np.number]).columns.tolist()

# If you want to specify KPI columns manually, uncomment and edit the line below
kpi_columns = ['Picking_Time', 'Order_Fulfillment', 'Picker_Utilization', 'Labor_Efficiency']  # Example KPI column names

# Compute confidence intervals for each KPI
confidence_level = 0.95
results = {}

for column in kpi_columns:
    kpi_values = data[column].dropna()  # Drop missing values
    n = len(kpi_values)
    if n < 2:
        print(f"Not enough data to compute confidence interval for {column}.")
        continue
    mean = np.mean(kpi_values)
    std_dev = np.std(kpi_values, ddof=1)  # Sample standard deviation
    t_value = t.ppf((1 + confidence_level) / 2, df=n-1)
    margin_of_error = t_value * (std_dev / np.sqrt(n))
    ci_lower = mean - margin_of_error
    ci_upper = mean + margin_of_error
    
    results[column] = {
        'Mean': mean,
        'Standard Deviation': std_dev,
        f'{int(confidence_level*100)}% CI Lower': ci_lower,
        f'{int(confidence_level*100)}% CI Upper': ci_upper
    }

# Convert results to a DataFrame for better visualization
results_df = pd.DataFrame(results).T

# Save the results to a new Excel file
output_file = 'confidence_intervals.xlsx'
results_df.to_excel(output_file, index=True)

print(f"Confidence interval analysis is complete. Results saved to {output_file}.")
