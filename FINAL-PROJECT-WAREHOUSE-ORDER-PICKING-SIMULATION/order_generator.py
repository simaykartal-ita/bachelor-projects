import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

# Set random seed for reproducibility
np.random.seed(20)

# Parameters
NUM_STORES = 46
NUM_DAYS = 30
STORE_IDS = [f"Store{i+1}" for i in range(NUM_STORES)]
START_DATE = datetime(2024, 12, 1)
OUTPUT_EXCEL_FILE = 'ORDERS_20.xlsx'  # Single Excel file with multiple sheets

# Simulation parameters per category
category_params = {
    'cam': {
        'ordering_stores_distribution': ('binomial', {'n':47, 'p':0.461338868707836}),
        'orders_per_store_distribution': ('normal', {'mean':134.1991554747082, 'std':49.752284250870034}),
        'skus_selected_distribution': ('normal', {'mean':19.014984355543778, 'std':6.590773602670962})
    },
    'camdışı': {
        'ordering_stores_distribution': ('binomial', {'n':30, 'p':0.7124444444444445}),
        'orders_per_store_distribution': ('normal', {'mean':118.19971631629788, 'std':52.172896309089516}),
        'skus_selected_distribution': ('lognormal', {'mu_log': np.log(7.808803968385981), 'sigma':0.38637726968964864})
    },
    'butik': {
        'ordering_stores_distribution': ('binomial', {'n':30, 'p':0.7106666666666667}),
        'orders_per_store_distribution': ('lognormal', {'mu_log': np.log(11.413836465376873), 'sigma':0.489025777292634}),
        'skus_selected_distribution': ('lognormal', {'mu_log': np.log(2.758444927170479), 'sigma':0.3649595135391025})
    }
}

# Path to the SKU weights Excel file
SKU_WEIGHTS_FILE = 'weights_topproducts_sold-Copy.xlsx'  # Ensure this file is in the same directory as the script

# Categories to process
CATEGORIES = ['cam', 'camdışı', 'butik']

# Check if the SKU weights file exists
if not os.path.exists(SKU_WEIGHTS_FILE):
    raise FileNotFoundError(f"The SKU weights file '{SKU_WEIGHTS_FILE}' does not exist in the current directory.")

# Function to read SKU data for a given category
def read_sku_data(file_path, sheet_name):
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except ValueError:
        raise ValueError(f"Worksheet named '{sheet_name}' not found in '{file_path}'. Please ensure the sheet exists.")
    except Exception as e:
        raise Exception(f"An error occurred while reading sheet '{sheet_name}': {e}")
    
    # Ensure required columns exist
    required_columns = ['Product id', 'Weight']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Sheet '{sheet_name}' must contain '{col}' column.")
    
    # Drop any rows with missing values in required columns
    df = df.dropna(subset=required_columns)
    
    # Convert 'Product id' to integer to ensure no decimal points
    try:
        df['Product id'] = df['Product id'].astype(float).astype(int)
    except ValueError:
        raise ValueError(f"Non-integer values found in 'Product id' column of sheet '{sheet_name}'. Please ensure all 'Product id's are integers.")
    
    # Check for duplicate Product IDs within the sheet
    if df['Product id'].duplicated().any():
        duplicates = df[df['Product id'].duplicated()]['Product id'].unique()
        raise ValueError(f"Duplicate 'Product id's found in sheet '{sheet_name}': {duplicates}. Please ensure all 'Product id's are unique.")
    
    # Check for non-positive weights
    if (df['Weight'] <= 0).any():
        invalid_weights = df[df['Weight'] <= 0]
        raise ValueError(f"Non-positive weights found in sheet '{sheet_name}':\n{invalid_weights}")
    
    return df

# Read SKU data for all categories
sku_data = {}
for category in CATEGORIES:
    print(f"Reading SKU data for category '{category}' from sheet '{category}'...")
    sku_df = read_sku_data(SKU_WEIGHTS_FILE, sheet_name=category)
    
    # Validate and normalize weights
    total_weight = sku_df['Weight'].sum()
    if not np.isclose(total_weight, 1.0, atol=1e-3):
        print(f"Warning: Weights for category '{category}' sum to {total_weight:.6f}, normalizing.")
        sku_df['Weight'] = sku_df['Weight'] / total_weight  # Normalize to sum to 1
    
    sku_data[category] = sku_df
    print(f"Finished reading and processing SKU data for category '{category}'.\n")

# Function to simulate orders for a single category
def simulate_orders(category, sku_df, params):
    orders = []
    SKU_IDS = sku_df['Product id'].tolist()
    weights = sku_df['Weight'].values

    for day in range(NUM_DAYS):
        current_day = day + 1  # Days count from 1 to 30
        
        # Sample number of stores ordering today
        dist_type, dist_params = params['ordering_stores_distribution']
        if dist_type == 'binomial':
            n = dist_params['n']
            p = dist_params['p']
            num_stores_ordering = np.random.binomial(n, p)
        else:
            raise ValueError(f"Unsupported distribution type for ordering stores: '{dist_type}'")
        
        # Ensure the number of stores ordering does not exceed NUM_STORES
        num_stores_ordering = min(num_stores_ordering, NUM_STORES)
        
        if num_stores_ordering == 0:
            continue  # No orders for this day

        # Select unique stores
        ordering_stores = np.random.choice(STORE_IDS, size=num_stores_ordering, replace=False)

        for store in ordering_stores:
            # Sample number of items ordered by this store today
            dist_type_order, dist_params_order = params['orders_per_store_distribution']
            if dist_type_order == 'normal':
                mean = dist_params_order['mean']
                std = dist_params_order['std']
                num_items_ordered = int(np.round(np.random.normal(mean, std)))
                num_items_ordered = max(0, num_items_ordered)  # Ensure non-negative
            elif dist_type_order == 'lognormal':
                mu_log = dist_params_order['mu_log']
                sigma = dist_params_order['sigma']
                num_items_ordered = int(np.round(np.random.lognormal(mean=mu_log, sigma=sigma)))
                num_items_ordered = max(0, num_items_ordered)  # Ensure non-negative
            else:
                raise ValueError(f"Unsupported distribution type for orders per store: '{dist_type_order}'")
            
            if num_items_ordered == 0:
                continue  # Skip if no items ordered

            # Sample number of SKUs to select for this order
            dist_type_sku, dist_params_sku = params['skus_selected_distribution']
            if dist_type_sku == 'normal':
                mean = dist_params_sku['mean']
                std = dist_params_sku['std']
                num_skus_selected = int(np.round(np.random.normal(mean, std)))
                num_skus_selected = max(1, num_skus_selected)  # Ensure at least 1 SKU is selected
            elif dist_type_sku == 'lognormal':
                mu_log = dist_params_sku['mu_log']
                sigma = dist_params_sku['sigma']
                num_skus_selected = int(np.round(np.random.lognormal(mean=mu_log, sigma=sigma)))
                num_skus_selected = max(1, num_skus_selected)  # Ensure at least 1 SKU is selected
            else:
                raise ValueError(f"Unsupported distribution type for SKUs selected: '{dist_type_sku}'")
            
            # Ensure the number of SKUs selected does not exceed available SKUs
            num_skus_selected = min(num_skus_selected, len(SKU_IDS))

            # Select SKUs based on their weights
            try:
                selected_skus = np.random.choice(SKU_IDS, size=num_skus_selected, replace=False, p=weights)
            except ValueError as ve:
                raise ValueError(f"Error selecting SKUs for category '{category}': {ve}")

            # Get weights for selected SKUs
            selected_weights = sku_df[sku_df['Product id'].isin(selected_skus)]['Weight'].values
            # Normalize selected weights to sum to 1
            selected_weights = selected_weights / selected_weights.sum()

            # **Deterministic Allocation: Distribute items based on exact proportions**
            exact_quantities = num_items_ordered * selected_weights
            sku_quantities = np.floor(exact_quantities).astype(int)
            remaining = num_items_ordered - sku_quantities.sum()

            if remaining > 0:
                fractional_parts = exact_quantities - sku_quantities
                # Get indices of the largest fractional parts
                indices = np.argsort(fractional_parts)[-remaining:]
                for idx in indices:
                    sku_quantities[idx] += 1

            for sku, qty in zip(selected_skus, sku_quantities):
                if qty > 0:
                    orders.append({
                        'Day': current_day,  # Day number from 1 to 30
                        'Store_ID': store,
                        'Product_ID': sku,
                        'Quantity': qty
                    })

    # Create DataFrame
    orders_df = pd.DataFrame(orders)

    # Ensure 'Product_ID' and 'Quantity' are integers
    if not orders_df.empty:
        orders_df['Product_ID'] = orders_df['Product_ID'].astype(int)
        orders_df['Quantity'] = orders_df['Quantity'].astype(int)
        orders_df['Day'] = orders_df['Day'].astype(int)

    # Optionally, sort the DataFrame
    orders_df.sort_values(by=['Day', 'Store_ID', 'Product_ID'], inplace=True)

    return orders_df

# Create a Pandas ExcelWriter object to write multiple sheets
with pd.ExcelWriter(OUTPUT_EXCEL_FILE, engine='openpyxl') as writer:
    # Main simulation loop for all categories
    for category in CATEGORIES:
        if category not in sku_data:
            print(f"Category '{category}' has no SKU data. Skipping simulation for this category.\n")
            continue

        print(f"Simulating orders for category: '{category}'")
        sku_df = sku_data[category]
        params = category_params[category]

        # Simulate orders for the category
        try:
            orders_df = simulate_orders(category, sku_df, params)
        except Exception as e:
            print(f"An error occurred during simulation for category '{category}': {e}\n")
            continue

        # Write the DataFrame to the appropriate sheet in the Excel file
        try:
            orders_df.to_excel(writer, sheet_name=category, index=False)
            print(f"Order data for category '{category}' has been added to '{OUTPUT_EXCEL_FILE}' as sheet '{category}'.\n")
        except Exception as e:
            print(f"An error occurred while writing to sheet '{category}': {e}\n")

    print(f"All simulations completed successfully. Consolidated data saved to '{OUTPUT_EXCEL_FILE}'.")
