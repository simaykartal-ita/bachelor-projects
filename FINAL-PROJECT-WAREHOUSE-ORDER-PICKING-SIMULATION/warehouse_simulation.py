import simpy
import random
import pandas as pd
from collections import defaultdict
import itertools

# Path to the Excel layout file
EXCEL_FILE_PATH = 'C:/Users/hasan/Desktop/boşluklardoldu_layout.xlsx'
ORDER_FILE_PATH = 'C:/Users/hasan/Desktop/ORDERS/ORDERS_3.xlsx'

# Parameters for multi-day simulation
NUM_DAYS = 12      # Number of days to simulate
DAY_LENGTH = 5400  # Length of each day in simulation time units

# Warehouse configuration constants
NUM_CORRIDORS = 21
SECTIONS_PER_ROW = 11
CHECKIN_CHECKOUT_POINT = (NUM_CORRIDORS, 'left', 0)  # Starting/ending point for pickers
ITEM_PICK_TIME = 4  # Item picking time
FIXED_REPLENISHMENT_TIME = 60
NUMBER_OF_PICKERS = 10

# Shipment parameters
SHIPMENT_CAPACITY = 100   # Max item capacity per shipment
FULLNESS_RATE = 0.8       # Fullness rate threshold for shipment departure
SAFETY_STOCK = 100
LOCATION_CAPACITY = 700
DAILY_UPPER_SHELF_ADDITION = 1000

# List to hold the summary log
summary_log = []

def split_order_items(items, max_capacity=100):
    """
    Split a list of (Product_ID, Quantity) into batches where each batch's total
    quantity does not exceed max_capacity. Uses ascending order by quantity.
    """
    # Sort items by quantity ascending
    sorted_items = sorted(items, key=lambda x: x[1])

    batches = []
    current_batch = []
    current_total = 0

    for product_id, quantity in sorted_items:
        while quantity > 0:
            available_capacity = max_capacity - current_total
            if available_capacity <= 0:
                # Current batch is full; start a new batch
                batches.append(current_batch)
                current_batch = []
                current_total = 0
                available_capacity = max_capacity

            if quantity <= available_capacity:
                # Add the remaining quantity to the current batch
                current_batch.append((product_id, quantity))
                current_total += quantity
                quantity = 0
            else:
                # Fill the current batch to max_capacity and reduce the remaining quantity
                current_batch.append((product_id, available_capacity))
                current_total += available_capacity
                quantity -= available_capacity

    # Append the last batch if it has any items
    if current_batch:
        batches.append(current_batch)

    return batches

class Engine:
    def __init__(self, env, num_pickers, order_file_path):
        self.env = env
        self.warehouse = Warehouse(env, EXCEL_FILE_PATH)  # Pass the file path here
        self.pickers = [Picker(env, f"Picker {i+1}", self.warehouse, self) for i in range(num_pickers)]
        self.order_queue = []
        self.replenishment_queue = []
        self.backorder_queue = []
        self.orders_fulfilled = 0
        self.total_orders = 0
        self.daily_log = []
        self.order_file_path = order_file_path  # Path to Excel file
        self.orders_by_day = defaultdict(list)  # Store orders by day
        self.SAFETY_STOCK = 100   # Set your safety stock threshold
        self.LOCATION_CAPACITY = 700
        self.DAILY_UPPER_SHELF_ADDITION = DAILY_UPPER_SHELF_ADDITION

        # Keep track of the current simulation day
        self.current_day = 0  # Will be updated in run_for_multiple_days()

        # Start pickers' work processes
        for picker in self.pickers:
            self.env.process(picker.work())

        # Start task assignment
        self.env.process(self.assign_tasks())

    def load_orders_from_excel(self):
        """Load orders from the Excel file, split them by day, and create Order objects."""
        if not self.order_file_path:
            print("Error: Order file path is not set.")
            return

        try:
            # Read all sheets into a dictionary of DataFrames with sheet names as keys
            all_sheets = pd.read_excel(self.order_file_path, sheet_name=None)
            print(f"Loaded {len(all_sheets)} sheets from Excel successfully.")

            # Add 'Category' column based on sheet name and concatenate all sheets
            df_list = []
            for sheet_name, sheet_df in all_sheets.items():
                sheet_df['Category'] = sheet_name  # Add category column
                df_list.append(sheet_df)
            df = pd.concat(df_list, ignore_index=True)
            print("Concatenated all sheets into a single DataFrame with 'Category' column.")

            # Ensure necessary columns exist
            required_columns = {'Day', 'Store_ID', 'Product_ID', 'Quantity', 'Category'}
            if not required_columns.issubset(df.columns):
                missing = required_columns - set(df.columns)
                print(f"Error: Missing columns in Excel file: {missing}")
                return

            # Group orders by 'Day', 'Store_ID', and 'Category', then aggregate quantities
            self.grouped_orders = (
                df.groupby(['Day', 'Store_ID', 'Category'])
                .apply(lambda x: list(zip(x['Product_ID'], x['Quantity'])))
                .to_dict()
            )

            # Split aggregated orders into batches and add them to orders_by_day
            for (day, store, category), items in self.grouped_orders.items():
                # Use the helper function to split items into batches of <=100
                batches = split_order_items(items, max_capacity=100)

                for batch in batches:
                    # Create a new Order for each batch
                    self.orders_by_day[day].append(Order(items=batch, store_id=store, category=category))
                    self.total_orders += 1  # Increment total orders count per order

            print("Orders grouped, batched, and split by day, store, and category with max 100 items per order.")

        except FileNotFoundError:
            print(f"Error: File not found at {self.order_file_path}")
        except Exception as e:
            print(f"Error loading Excel file: {e}")

    def process_orders_per_day(self, current_day):
        """Push the orders for `current_day` into the queue."""
        print(f"Processing orders for Day {current_day}")
        daily_orders = self.orders_by_day.get(current_day, [])
        for order in daily_orders:
            self.order_queue.append(order)
        self.total_orders += len(daily_orders)

    def assign_tasks(self):
        """
        Continuously assign tasks (orders/backorders/replenishments) to free pickers,
        prioritizing backorders, then replenishments, then new orders.
        """
        while True:
            for picker in self.pickers:
                if not picker.busy:
                    # Prioritize backorders
                    if self.backorder_queue:
                        task = self.backorder_queue.pop(0)
                        self.env.process(picker.fulfill_order(task, is_backorder=True))
                    # Handle replenishment tasks
                    elif self.replenishment_queue:
                        task = self.replenishment_queue.pop(0)
                        self.env.process(picker.replenish(task))
                    # Assign orders from the order queue
                    elif self.order_queue:
                        task = self.order_queue.pop(0)
                        self.env.process(picker.fulfill_order(task))
                        self.orders_fulfilled += len(task.items)  # Update fulfilled orders count
            yield self.env.timeout(1)

    def run_for_multiple_days(self, num_days, day_length):
        """Run the simulation for multiple days, one day at a time."""
        for day in range(1, num_days + 1):
            self.current_day = day  # <-- Mark the simulation day
            print(f"--- Starting Day {day} ---")
            self.process_orders_per_day(day)
            print(f"Running simulation for Day {day}")
            self.env.run(until=self.env.now + day_length)

            # After the day ends, restock upper shelves
            self.daily_upper_shelf_restock(day)
            self.generate_daily_summary(day, self.env.now)

        # After all days are completed, compute and print KPIs
        self.compute_kpis()

    def daily_upper_shelf_restock(self, day):
        """
        Add DAILY_UPPER_SHELF_ADDITION units of each SKU to every location's upper shelf.
        Log this event to summary_log.
        """
        # Identify all unique SKUs from the warehouse
        unique_skus = set()
        for location, shelves in self.warehouse.storage.items():
            unique_skus.update(shelves['bottom'])
            unique_skus.update(shelves['upper'])

        # Add items to upper shelves
        start_time = self.env.now
        for location, shelves in self.warehouse.storage.items():
            for sku in unique_skus:
                shelves['upper'].extend([sku] * self.DAILY_UPPER_SHELF_ADDITION)

        completion_time = self.env.now
        task_log = {
            "picker": "System",
            "task_type": "Daily Upper Shelf Restock",
            "start_time": start_time,
            "completion_time": completion_time,
            "order_items": "N/A",
            "collected_items": [(sku, self.DAILY_UPPER_SHELF_ADDITION) for sku in unique_skus],
            "lost_items": [],
            "route": "N/A",
            "Day": self.current_day  # <-- Tag the correct day
        }
        summary_log.append(task_log)
        print(f"Daily upper shelf restock done for day {day}.")

    def generate_daily_summary(self, day, total_time):
        """Collect logs that were completed on `day` only."""
        print(f"\n--- End of Day {day} ---")
        # Only pick tasks whose 'Day' matches exactly
        daily_tasks = [log for log in summary_log if log.get('Day') == day]

        print(f"Tasks logged today: {len(daily_tasks)}")

        if daily_tasks:
            daily_df = pd.DataFrame(daily_tasks)
            daily_df['Day'] = day
            self.daily_log.append(daily_df)

    def compute_kpis(self):
        """Compute and print some high-level KPIs from the summary log."""
        total_picking_time = 0
        picking_task_count = 0
        fulfillment_ratios = []

        # Process each task in the summary_log
        for log in summary_log:
            if log['task_type'] in ["Order Fulfillment", "Backorder Fulfillment"]:
                # Calculate picking time for the task
                task_duration = log['completion_time'] - log['start_time']
                total_picking_time += task_duration
                picking_task_count += 1

                # Calculate fulfillment ratio
                if isinstance(log['order_items'], list):
                    ordered_quantity = sum(quantity for _, quantity in log['order_items'])
                else:
                    ordered_quantity = 0

                if isinstance(log['collected_items'], list):
                    collected_quantity = sum(quantity for _, quantity in log['collected_items'])
                else:
                    collected_quantity = 0

                if ordered_quantity > 0:
                    fulfillment_ratio = collected_quantity / ordered_quantity
                    fulfillment_ratios.append(fulfillment_ratio)

        # Calculate average picking time per order
        avg_picking_time = total_picking_time / picking_task_count if picking_task_count else 0

        # Calculate average order fulfillment ratio
        avg_fulfillment_ratio = sum(fulfillment_ratios) / len(fulfillment_ratios) if fulfillment_ratios else 0

        # Calculate average picker utilization
        total_simulation_time = NUM_DAYS * DAY_LENGTH
        total_busy_time = sum(picker.total_busy_time for picker in self.pickers)
        avg_picker_utilization = (total_busy_time / (NUMBER_OF_PICKERS * total_simulation_time)) * 100 if total_simulation_time else 0

        # Calculate Labor Efficiency
        orders_processed = sum(
            1
            for log in summary_log
            if log['task_type'] in ["Order Fulfillment", "Backorder Fulfillment", "Replenishment"]
        )
        labor_efficiency = orders_processed / total_busy_time if total_busy_time > 0 else 0

        print("\n--- Simulation KPIs ---")
        print(f"Average Picking Time per Order: {avg_picking_time:.2f} time units")
        print(f"Average Order Fulfillment Ratio: {avg_fulfillment_ratio * 100:.2f}%")
        print(f"Average Picker Utilization: {avg_picker_utilization:.2f}%")
        print(f"Labor Efficiency: {labor_efficiency:.4f} orders processed per time unit")

    def save_to_excel(self, output_path="simulation_results.xlsx"):
        """Save the accumulated daily logs to an Excel file."""
        if self.daily_log:
            # Concatenate all daily DataFrames
            full_log = pd.concat(self.daily_log, ignore_index=True)
            with pd.ExcelWriter(output_path) as writer:
                full_log.to_excel(writer, index=False, sheet_name='Tasks_Log')
            print(f"Simulation results saved to {output_path}")
        else:
            print("No logs to save.")

    def create_replenishment_tasks(self):
        """
        Check all items in bottom shelves; if below safety stock, create replenishment tasks.
        """
        warehouse_snapshot = self.warehouse.storage
        item_counts = defaultdict(int)
        location_item_types = defaultdict(set)

        for location, shelves in warehouse_snapshot.items():
            bottom_items = shelves['bottom']
            for it in bottom_items:
                item_counts[it] += 1
                location_item_types[location].add(it)

        # Now check which items are below safety stock
        for item_type, count in item_counts.items():
            if count < self.SAFETY_STOCK:
                # Identify candidate locations for replenishment
                candidate_locations = []
                for location, shelves in warehouse_snapshot.items():
                    if item_type in shelves['bottom']:
                        candidate_locations.append(location)

                for loc in candidate_locations:
                    num_item_types = len(location_item_types[loc])
                    replenish_amount = self.LOCATION_CAPACITY // num_item_types if num_item_types else self.LOCATION_CAPACITY

                    # Check if upper shelf has the item
                    upper_items = warehouse_snapshot[loc]['upper']
                    if item_type in upper_items:
                        task = {
                            'location': loc,
                            'item_type': item_type,
                            'amount': replenish_amount
                        }
                        self.replenishment_queue.append(task)


class Warehouse:
    def __init__(self, env, excel_file_path):
        self.env = env
        self.excel_file_path = excel_file_path
        self.storage = self.initialize_storage()

    def initialize_storage(self):
        """Initialize the warehouse storage based on an Excel layout."""
        try:
            warehouse_df = pd.read_excel(self.excel_file_path)
            print("[DEBUG] Warehouse layout loaded successfully.")
        except FileNotFoundError:
            print(f"Error: File not found at path {self.excel_file_path}")
            return {}
        except Exception as e:
            print(f"Error loading warehouse layout: {e}")
            return {}

        storage = {}
        for _, row in warehouse_df.iterrows():
            try:
                corridor = int(row['Corridor No'])
                side = row['Side'].strip().lower()  # Ensure consistent casing
                section = int(row['Section No'])
                product = int(row['Product'])  # Convert to int
                quantity = int(row['Quantity'])

                location = (corridor, side, section)
                if location not in storage:
                    storage[location] = {'bottom': [], 'upper': []}

                # Fill both bottom and upper shelves with the same products and quantities
                products = [product] * quantity
                storage[location]['bottom'].extend(products)
                storage[location]['upper'].extend(products)
            except (ValueError, KeyError) as e:
                print(f"[DEBUG] Skipping invalid row: {row.to_dict()} due to {e}")
                continue

        return storage

    def pick_item(self, location, item_type, shelf='bottom'):
        """Pick one instance of `item_type` from the specified shelf."""
        shelf_items = self.storage[location][shelf]
        if item_type in shelf_items:
            shelf_items.remove(item_type)
            return True
        return False

    def replenish_item(self, location, item_type, amount):
        """
        Move up to `amount` of `item_type` from upper shelf to bottom shelf
        if available on upper shelf.
        """
        upper_shelf = self.storage[location]['upper']
        available_up = upper_shelf.count(item_type)
        to_move = min(available_up, amount)

        if to_move > 0:
            # Remove from upper
            for _ in range(to_move):
                upper_shelf.remove(item_type)
            # Add to bottom
            self.storage[location]['bottom'].extend([item_type]*to_move)

    def get_snapshot(self):
        """Generate a snapshot of the current warehouse storage."""
        snapshot = {}
        for location, shelves in self.storage.items():
            snapshot[location] = {
                'Bottom Items': shelves['bottom'],
                'Upper Items': shelves['upper']
            }
        return pd.DataFrame.from_dict(snapshot, orient='index')

    def find_product_locations(self, item_type):
        """Find all locations containing the specified product in bottom shelves."""
        return [loc for loc, shelves in self.storage.items() if item_type in shelves['bottom']]

    def count_item(self, location, item_type, shelf='bottom'):
        """Count how many of a given item are available at a location's shelf."""
        return self.storage[location][shelf].count(item_type)

    def pick_items(self, location, item_type, amount, shelf='bottom'):
        """
        Attempt to pick 'amount' of 'item_type' from the given location shelf.
        Return the number of items actually picked.
        """
        shelf_items = self.storage[location][shelf]
        picked = 0
        for _ in range(amount):
            try:
                shelf_items.remove(item_type)
                picked += 1
            except ValueError:
                break
        return picked


class Picker:
    def __init__(self, env, name, warehouse, engine):
        self.env = env
        self.name = name
        self.warehouse = warehouse
        self.engine = engine
        self.busy = False
        self.total_busy_time = 0
        self.last_busy_start_time = None

    def work(self):
        """Continuously pull tasks from the engine's queues."""
        while True:
            if not self.busy:
                if self.engine.backorder_queue:
                    task = self.engine.backorder_queue.pop(0)
                    self.env.process(self.fulfill_order(task, is_backorder=True))
                elif self.engine.replenishment_queue:
                    task = self.engine.replenishment_queue.pop(0)
                    self.env.process(self.replenish(task))
                elif self.engine.order_queue:
                    task = self.engine.order_queue.pop(0)
                    self.env.process(self.fulfill_order(task))
            yield self.env.timeout(1)

    def fulfill_order(self, order, is_backorder=False):
        """Fulfill an order or backorder."""
        self.start_busy()
        start_time = self.env.now
        task_type = "Backorder Fulfillment" if is_backorder else "Order Fulfillment"

        current_location = CHECKIN_CHECKOUT_POINT
        route = [current_location]
        items_collected, lost_items = [], []
        total_travel_time = 0

        for item, requested_quantity in order.items:
            quantity_needed = requested_quantity
            total_picked_for_item = 0

            # Search for item across locations until quantity is fulfilled
            while quantity_needed > 0:
                next_location, travel_time = self.find_nearest_item(current_location, item)
                if next_location is None:
                    # No location has this item
                    break

                # Travel to that location
                route.append(next_location)
                available = self.warehouse.count_item(next_location, item)

                if available > 0:
                    to_pick = min(available, quantity_needed)
                    picked = self.warehouse.pick_items(next_location, item, to_pick)
                    if picked > 0:
                        total_picked_for_item += picked
                        quantity_needed -= picked
                        total_travel_time += travel_time + (ITEM_PICK_TIME * picked)
                        current_location = next_location
                    else:
                        break
                else:
                    break

            if total_picked_for_item > 0:
                items_collected.append((item, total_picked_for_item))
            if quantity_needed > 0:
                lost_items.append((item, quantity_needed))

        # Return to the starting point
        return_travel_time = self.calculate_distance(current_location, CHECKIN_CHECKOUT_POINT)
        total_travel_time += return_travel_time
        route.append(CHECKIN_CHECKOUT_POINT)

        yield self.env.timeout(total_travel_time)
        self.stop_busy()

        completion_time = self.env.now
        task_log = {
            "picker": self.name,
            "task_type": task_type,
            "store_id": order.store_id,
            "category": order.category,
            "start_time": start_time,
            "completion_time": completion_time,
            "order_items": order.items,
            "collected_items": items_collected,
            "lost_items": lost_items,
            "route": " -> ".join(map(str, route)),
            "Day": self.engine.current_day  # <-- Record the day
        }
        summary_log.append(task_log)

        # Potentially create replenishment tasks
        self.engine.create_replenishment_tasks()

    def replenish(self, task):
        """Perform a replenishment task."""
        self.start_busy()
        start_time = self.env.now
        location, item_type, amount = task['location'], task['item_type'], task['amount']

        route = [CHECKIN_CHECKOUT_POINT]
        travel_time = self.calculate_distance(CHECKIN_CHECKOUT_POINT, location)
        yield self.env.timeout(travel_time)
        route.append(location)

        self.warehouse.replenish_item(location, item_type, amount)

        # Return to start with extra time
        return_time = self.calculate_distance(location, CHECKIN_CHECKOUT_POINT)*3 + FIXED_REPLENISHMENT_TIME
        yield self.env.timeout(return_time)
        route.append(CHECKIN_CHECKOUT_POINT)

        self.stop_busy()
        completion_time = self.env.now
        task_log = {
            "picker": self.name,
            "task_type": "Replenishment",
            "start_time": start_time,
            "completion_time": completion_time,
            "order_items": "N/A",
            "collected_items": [(item_type, amount)],
            "lost_items": [],
            "route": " -> ".join(map(str, route)),
            "Day": self.engine.current_day  # <-- Record the day
        }
        summary_log.append(task_log)

    def find_shortest_route(self, locations):
        """
        Simple TSP-like solution using a greedy nearest-neighbor algorithm.
        """
        unvisited = set(locations[1:])
        current_location = locations[0]
        route = [current_location]
        total_distance = 0

        while unvisited:
            next_location = min(unvisited, key=lambda loc: self.calculate_distance(current_location, loc))
            distance = self.calculate_distance(current_location, next_location)
            route.append(next_location)
            total_distance += distance
            current_location = next_location
            unvisited.remove(next_location)

        distance_to_start = self.calculate_distance(current_location, locations[0])
        route.append(locations[0])
        total_distance += distance_to_start
        return route, total_distance

    def find_nearest_item(self, current_location, item_type):
        """Find the nearest location that has `item_type` in its bottom shelf."""
        nearest_location = None
        shortest_distance = float('inf')

        for location, shelves in self.warehouse.storage.items():
            if item_type in shelves['bottom']:
                distance = self.calculate_distance(current_location, location)
                if distance < shortest_distance:
                    nearest_location = location
                    shortest_distance = distance

        return (nearest_location, shortest_distance) if nearest_location else (None, None)

    def calculate_distance(self, loc1, loc2):
        corridor1, side1, section1 = loc1
        corridor2, side2, section2 = loc2
        # Manhattan distance (corridor difference + section difference)
        return abs(corridor1 - corridor2) + abs(section1 - section2)

    def start_busy(self):
        self.busy = True
        self.last_busy_start_time = self.env.now

    def stop_busy(self):
        if self.last_busy_start_time is not None:
            self.total_busy_time += self.env.now - self.last_busy_start_time
        self.busy = False
        self.last_busy_start_time = None


class Order:
    def __init__(self, items, store_id=None, category=None):
        self.items = items
        self.store_id = store_id
        self.category = category

    def __str__(self):
        return f"Order for Store {self.store_id}, Category '{self.category}' with items: {self.items}"

    def __repr__(self):
        return self.__str__()


# --- Initialize and run the simulation ---

if __name__ == "__main__":
    env = simpy.Environment()
    engine = Engine(env, num_pickers=NUMBER_OF_PICKERS, order_file_path=ORDER_FILE_PATH)

    # Load orders into the engine
    engine.load_orders_from_excel()

    # Run the simulation for multiple days
    engine.run_for_multiple_days(NUM_DAYS, DAY_LENGTH)

    # Save simulation results to Excel
    engine.save_to_excel("upper-added_son_3.xlsx")
