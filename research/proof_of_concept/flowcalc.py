from typing import List

#!/usr/bin/env python
# coding: utf-8

# <a href="https://colab.research.google.com/github/GregKyri/Greg-Kyritsakas/blob/main/flowcalc.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

# # ***Calculate daily nominal flow in m3/day***
# 

# In[ ]:


def calculate_flow_per_lane(
    lanes: int,
    daily_flow: List[float],
) -> List[float]:
    return [flow / lanes for flow in daily_flow]


def lppd_to_m3phr(flow_in_liter_per_day: float):
    return flow_in_liter_per_day / 1000 / 24

def calculate_flow_per_unit(
    units: int,
    flow_per_lane: List[float]
) -> List[float]:
    return [flow / units for flow in flow_per_lane]

def calculate_demand_population_from_statistics(
    population_persons: int,
    consumption_lppd: float,  # consumption as in liter per person per day
):
    """Calculates demand from population persons and (average/min/max) 
    consumption .

    Args:
        population_persons (int): number of persons
        consumption_lppd (float): consumption in liter per person per day

    Returns:
        float: water demand from population
    """
    return population_persons * lppd_to_m3phr(consumption_lppd)


def calculate_all_water_demand(
    population_persons: int,
    consumption_lppd: float | None,
    demand_industry: float,
    demand_agriculture: float,
    leakage_factor: float,
):
    demand_population = calculate_demand_population_from_statistics(
            population_persons=population_persons, 
            consumption_lppd=consumption_lppd)
    demand_total = demand_population + demand_industry + demand_agriculture
    return demand_total * (1 + leakage_factor)

def calculate_daily_flow(
    leakage_factor: float,
    population_growth: List[int],
    min_consumption_lppd: float,
    max_consumption_lppd: float,
    med_consumption_lppd: float | None = None,
    demand_industry: float | None = None,
    demand_agriculture: float | None = None,
    daily_flow: List[float] | None = None,
) -> List[float]:
    
    if daily_flow is None:
        daily_flow = []
    
    if med_consumption_lppd is None:
        med_consumption_lppd = 0.
    for no_persons in population_growth:
        demand_kwargs = dict(
            leakage_factor=leakage_factor,
            population_persons=no_persons, 
            demand_industry=demand_industry,
            demand_agriculture=demand_agriculture,
            )
        (
            demand_min,
            demand_max,
            ) = (
                calculate_all_water_demand(
                    consumption_lppd=min_consumption_lppd, **demand_kwargs),
                calculate_all_water_demand(
                    consumption_lppd=max_consumption_lppd, **demand_kwargs),
            )
        daily_flow.append(demand_min)
        if med_consumption_lppd is not None:
            demand_med = calculate_all_water_demand(
                    consumption_lppd=med_consumption_lppd, **demand_kwargs)
            daily_flow.append(demand_med)
        daily_flow.append(demand_max)
        # daily_flow.append(((no_persons * to_m3perhour(med_consumption_lppd)) + irgflow + industflow) * (1 + leak))
        # daily_flow.append(((no_persons * to_m3perhour(max_consumption_lppd)) + irgflow + industflow) * (1 + leak))
    return daily_flow


def flowcalc():
    # Calculate daily flow
    pop = []
    watercons = []
    leak = 0
    irig = ""
    indust = ""

    # User input for population number
    while True:
        pop_str = input("Population numbers (comma-separated):")
        pop_list = pop_str.split(',')
        try:
            pop = [float(num) for num in pop_list]
            break
        except ValueError:
            print("Invalid input. Please enter a valid population number.")

    # User input for water consumption per person per day
    while True:
        watercons_str = input("Water consumption per person per day (l/p/day): ")
        try:
            watercons.append(float(watercons_str))
            break
        except ValueError:
            print("Invalid input. Please enter a valid water consumption value.")

    flowsteps = len(pop)

    # User input for leakage estimation
    while True:
        leak_str = input("Leakage estimation (0-1): ")
        try:
            leak = float(leak_str)
            break
        except ValueError:
            print("Invalid input. Please enter a valid leakage estimation value.")

    # User input for irrigation needs
    irig = input("Are there any irrigation needs? (Yes/No): ").strip().capitalize()

    # User input for industrial needs
    indust = input("Are there any industrial needs? (Yes/No): ").strip().capitalize()

    # Initialize irrigation and industrial flow
    irgflow = 0
    industflow = 0

    if irig == "Yes":
        while True:
            irgflow_str = input("Irrigation flow (m3/day):")
            try:
                irgflow = float(irgflow_str)
                break
            except ValueError:
                print("Invalid input. Please enter a valid irrigation flow value.")

    if indust == "Yes":
        while True:
            industflow_str = input("Industrial flow (m3/day):")
            try:
                industflow = float(industflow_str)
                break
            except ValueError:
                print("Invalid input. Please enter a valid industrial flow value.")

    # User input for consumption periods
    while True:
        flowpat_str = input("Set the number of different consumption periods: ")
        try:
            flowpat = int(flowpat_str)
            if flowpat >= 1:
                break
            else:
                print("Invalid input. Please enter a number greater than or equal to 1.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

    dailyflow = []

    if flowpat == 2:
        setmax_str = input("Maximum water consumption per person per day (l/p/day): ")
        try:
            setmax = float(setmax_str)
            setmin = watercons[0]
            for i in range(flowsteps):
                dailyflow.append(((pop[i] * (setmin / 1000)) + irgflow + industflow) * (1 + leak))
                dailyflow.append(((pop[i] * (setmax / 1000)) + irgflow + industflow) * (1 + leak))
        except ValueError:
            print("Invalid input. Please enter a valid maximum consumption value.")
    elif flowpat > 2:
        setmax_str = input("Maximum water consumption per person per day (l/p/day):")
        setmed_str = input("Intermediate water consumption per person per day (l/p/day):")
        try:
            setmax = float(setmax_str)
            setmed = float(setmed_str)
            setmin = watercons[0]
            for i in range(flowsteps):
                dailyflow.append(((pop[i] * (setmin / 1000)) + irgflow + industflow) * (1 + leak))
                dailyflow.append(((pop[i] * (setmed / 1000)) + irgflow + industflow) * (1 + leak))
                dailyflow.append(((pop[i] * (setmax / 1000)) + irgflow + industflow) * (1 + leak))
        except ValueError:
            print("Invalid input. Please enter a valid maximum consumption value.")
    else:
        for i in range(flowsteps):
            dailyflow.append(pop[i] * (watercons[0] / 1000) * (1 + leak) + irgflow + industflow)

    # Number of lanes/number of units/flow per lane
    while True:
        lanes_str = input("Set the number of independent lanes: ")
        try:
            lanes = int(lanes_str)
            if lanes >= 1:
                break
            else:
                print("Invalid input. Please enter a number greater than or equal to 1.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

    while True:
        units_str = input("Number of units per lane:")
        try:
            units = int(units_str)
            if units >= 1:
                break
            else:
                print("Invalid input. Please enter a number greater than or equal to 1.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

    flowlane = [flow / lanes for flow in dailyflow]
    flowunit = [flow / units for flow in flowlane]

    return dailyflow, lanes, units, flowlane, flowunit

# Example usage:
# dailyflow, lanes, units, flowlane, flowunit = flowcalc()

