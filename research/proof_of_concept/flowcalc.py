from typing import List
import numpy as np

#!/usr/bin/env python
# coding: utf-8

# <a href="https://colab.research.google.com/github/GregKyri/Greg-Kyritsakas/blob/main/flowcalc.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

# # ***Calculate daily nominal flow in m3/day***
# 

# In[ ]:

### https://nicoco007.github.io/Propagation-of-Uncertainty-Calculator/


def calculate_flow_per_lane(
    lanes: int,
    daily_flow_list: List[float],
) -> list[float]:
    return [flow / lanes for flow in daily_flow_list]


def lppd_to_m3phr(flow_in_liter_per_day: float):
    return flow_in_liter_per_day / 1000 / 24


def calculate_flow_per_unit(
    units: int,
    flow_per_lane_list: list[float]
) -> list[float]:
    return [flow / units for flow in flow_per_lane_list]


def calculate_water_demand_phr_for_population(
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


def calculate_total_water_demand_phr(
    population_persons: int,
    consumption_lppd: float,
    demand_industry_m3pd: float,
    demand_agriculture_m3pd: float,
    leakage_factor: float,
):
    demand_population = calculate_water_demand_phr_for_population(
            population_persons=population_persons,
            consumption_lppd=consumption_lppd)
    demand_total = (
        demand_population + demand_industry_m3pd/24 +
        demand_agriculture_m3pd/24
    )
    return demand_total * (1 + leakage_factor)


def var_population(
    delta_population: float,
    consumption_lppd: float,
    leakage_factor: float
) -> float:
    var_p = (
        (consumption_lppd/24000 * (leakage_factor + 1)) * delta_population)**2
    return var_p


def var_leakage_factor(
    delta_leakage_factor: float,
    population_persons: float,
    consumption_lppd: float,
    demand_industry: float = 0.,
    demand_agriculture: float = 0.,
):
    var_L = (
        (population_persons/24000 * consumption_lppd + demand_agriculture
         + demand_industry) * delta_leakage_factor
        )**2
    return var_L


def var_demand_agriculture(
    delta_demand_agriculture: float,
    leakage_factor: float,
):
    var_demand_agri = ((leakage_factor + 1) * delta_demand_agriculture)**2
    return var_demand_agri


def var_demand_industry(
    delta_demand_industry: float,
    leakage_factor: float,
):
    var_demand_industry = ((leakage_factor + 1) * delta_demand_industry)**2
    return var_demand_industry


def var_consumption_lppd(
    delta_consumption_lppd: float,    
    population_persons: float,
    leakage_factor: float,
    demand_industry: float = 0.,
    demand_agriculture: float = 0.,
):
    var_cons = (
        (population_persons/24000 * (1 + leakage_factor)
         ) * delta_consumption_lppd)**2
    return var_cons


def var_total_water_demand(
    delta_population: float,
    delta_leakage_factor: float,
    delta_consumption_lppd: float,
    delta_demand_industry: float,
    delta_demand_agriculture: float,
    leakage_factor: float,
    population_persons: int | float,
    consumption_lppd: float,
    demand_industry: float | None = None,
    demand_agriculture: float | None = None,
) -> float:
    if demand_agriculture is None:
        demand_agriculture = 0.
    if demand_industry is None:
        demand_industry = 0.
    var_persons = var_population(
        delta_population, consumption_lppd, leakage_factor)
    var_leakage = var_leakage_factor(
        delta_leakage_factor,
        population_persons,
        consumption_lppd,
        demand_industry,
        demand_agriculture)   
    var_demand_agr = var_demand_agriculture(
        delta_demand_agriculture,
        leakage_factor)
    var_demand_ind = var_demand_industry(delta_demand_industry, leakage_factor)
    var_cons_lppd = var_consumption_lppd(
        delta_consumption_lppd, population_persons, leakage_factor,
        demand_industry, demand_agriculture)
    return (
        var_persons + var_leakage + var_demand_agr + var_demand_ind +
        var_cons_lppd
        )


def stdev(variance: float):
    return float(np.sqrt(variance))


def calculate_flow_phr(
    leakage_factor: float,
    population_growth: list[int] | list[float],
    min_consumption_lppd: float,
    max_consumption_lppd: float,
    med_consumption_lppd: float | None = None,
    demand_industry_m3pd: float | None = None,
    demand_agriculture_m3pd: float | None = None,
    flow_phr: List[float] | None = None,
) -> List[float]:

    if demand_industry_m3pd is None:
        demand_industry_m3pd = 0.
    if demand_agriculture_m3pd is None:
        demand_agriculture_m3pd = 0.
    if flow_phr is None:
        flow_phr = []
    if med_consumption_lppd is None:
        med_consumption_lppd = 0.
    for no_persons in population_growth:
        demand_kwargs = dict(
            leakage_factor=leakage_factor,
            population_persons=no_persons,
            demand_industry=demand_industry_m3pd,
            demand_agriculture=demand_agriculture_m3pd,
            )
        (
            demand_min,
            demand_max,
            ) = (
                calculate_total_water_demand_phr(
                    consumption_lppd=min_consumption_lppd, **demand_kwargs),
                calculate_total_water_demand_phr(
                    consumption_lppd=max_consumption_lppd, **demand_kwargs),
            )
        flow_phr.append(demand_min)
        if med_consumption_lppd is not None:
            demand_med = calculate_total_water_demand_phr(
                    consumption_lppd=med_consumption_lppd, **demand_kwargs)
            flow_phr.append(demand_med)
        flow_phr.append(demand_max)
    return flow_phr


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


if __name__ == '__main__':
    population_growth = [1.1e5, 1.2e5, 2e5]
    delta_population = population_growth[0] * .1
    leakage_factor = 0.2
    delta_leakage_factor = 0.1
    cons_lppd = 90.
    delta_cons_lppd = cons_lppd * .1
    demand_agriculture = 2000
    demand_industry = 2000
    delta_demand_agriculture = demand_agriculture * .1
    delta_demand_industry = demand_industry * .1

    dailyflow = calculate_flow_phr(
        leakage_factor=leakage_factor,
        population_growth=population_growth,
        min_consumption_lppd=cons_lppd,
        max_consumption_lppd=130.,
        demand_agriculture_m3pd=demand_agriculture,
        demand_industry_m3pd=demand_industry
        )
    flow_per_lane = calculate_flow_per_lane(lanes=2, daily_flow_list=dailyflow)
    flow_per_unit = calculate_flow_per_unit(
        units=3, flow_per_lane_list=flow_per_lane)
    var_water_demand = var_total_water_demand(
        delta_population=delta_population,
        delta_leakage_factor=delta_leakage_factor,
        delta_consumption_lppd=delta_cons_lppd,
        delta_demand_agriculture=delta_demand_agriculture,
        delta_demand_industry=delta_demand_industry,
        population_persons=population_growth[0],
        leakage_factor=leakage_factor,
        consumption_lppd=cons_lppd,
        demand_industry=demand_industry,
        demand_agriculture=demand_agriculture)
    uncertainty_water_demand = stdev(var_water_demand)
