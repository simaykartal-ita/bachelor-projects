# Warehouse Order Picking Simulation & Optimization

**Industrial Engineering Final Project — Fall 2024**

This project was completed as the **final graduation project of the Industrial Engineering undergraduate program**, bringing together the analytical, optimization, simulation, and data-driven problem-solving skills developed throughout the degree.

Conducted in collaboration with **Şişecam**, the project focused on a real-world warehouse optimization problem involving the storage and order-picking operations of fragile glassware products. The study combined **operations research, data analysis, statistical modeling, simulation, logistics, inventory management, and process optimization** to evaluate the existing system and develop improvement alternatives.

Historical order data, the existing warehouse layout, and observations from warehouse visits were used to understand the current operation. A **discrete-event simulation model in Python using SimPy** was then developed to represent order generation, picker movements, inventory levels, replenishment, backorders, and daily warehouse operations.

The main objective was to improve warehouse efficiency by reducing picking time and unnecessary travel, improving resource utilization, and testing alternative warehouse layouts and order-picking strategies under realistic operational constraints.

## Methodology

Historical demand data was analyzed to model daily order quantities, active stores, and product variety. The original product range was reduced to **300 representative SKUs**, primarily based on sales frequency.

Randomized orders were generated using fitted demand distributions and **Monte Carlo simulation**. These orders were processed through a **discrete-event warehouse simulation** developed with SimPy.

Several operational scenarios were evaluated, including:

- Different numbers of warehouse pickers
- Alternative placement of best-selling products
- Warehouse layouts with and without product-category constraints
- Alternative category-based picking strategies
- Inventory replenishment and backorder processes

The main performance measures were **average picking time, order fulfillment ratio, and picker utilization**.

## Results

The initial model indicated that using 20 pickers resulted in substantial underutilization. Reducing the workforce to **10 pickers** created a more balanced baseline for subsequent experiments.

The most significant improvement was achieved by relocating best-selling products closer to the picking area. In the unconstrained alternative layout, average picking time decreased from **294.07 to 263.40 time units**, corresponding to an improvement of approximately **10.4%**, while the order fulfillment ratio remained around **98.5%**.

Alternative scenarios preserving the existing category constraints produced smaller improvements, highlighting the trade-off between operational efficiency and the handling requirements of fragile glassware products. :contentReference[oaicite:0]{index=0} :contentReference[oaicite:1]{index=1}

## Technologies & Methods

`Python` · `SimPy` · `Pandas` · `NumPy` · `Monte Carlo Simulation` · `Discrete-Event Simulation` · `Warehouse Optimization` · `Data Analysis`

## Project Files

```text
FINAL-PROJECT-WAREHOUSE-ORDER-PICKING-SIMULATION/
├── README.md
├── warehouse_simulation.py
├── order_generator.py
└── confidence_interval_analysis.py
```

- **warehouse_simulation.py** — Core warehouse simulation and KPI calculation
- **order_generator.py** — Randomized order generation based on historical demand
- **confidence_interval_analysis.py** — Statistical evaluation of simulation results

## Project Team

**Simay Kartal · Gizem Ergin · Hasan Yağız Kılıç**

**Project Advisor:** Taner Bilgiç
