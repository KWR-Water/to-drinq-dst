def construction_costs_total(
        construction_costs: float,
        plc_costs: float,
        construction_costs_percentage: float = 20.0,
        tail_costs_percentage: float = 15.0,
        general_facilities_costs_percentage: float = 5.0,
        ):
    """
    Calculate the investment costs over the lifespan of an asset.

    Parameters:
    construction_costs (float): The total construction costs of the asset.
    plc_costs (float): The total PLC costs of the asset.
    construction_costs_percentage (float): The percentage of construction
        costs.
    tail_costs_percentage (float): The percentage of tail costs.
    general_facilities_costs_percentage (float): The percentage of general
        facilities costs.

    Returns:
        float: The investment costs over the lifespan of the asset.
    """
    construction_costs_factor = (
        (1 + construction_costs_percentage / 100) * (
            1 + tail_costs_percentage / 100) * (
                1 + general_facilities_costs_percentage / 100)
    )
    construction_costs_total = (
        construction_costs + plc_costs) * construction_costs_factor
    return construction_costs_total


def interest_and_depreciation(
        construction_costs: float,
        interest_rate: float,
        lifespan_years: int):
    """
    Calculate the annual interest and depreciation costs.

    Parameters:
    construction_costs (float): The total construction costs of the asset.
    interest_rate (float): The annual interest rate (as a decimal).
    lifespan_years (int): The lifespan of the asset in years.

    Returns:
    float: The annual interest and depreciation costs.
    """
    if lifespan_years <= 0:
        raise ValueError("Lifespan must be greater than zero.")
    annual_depreciation = construction_costs / lifespan_years
    annual_interest = construction_costs * interest_rate
    return annual_depreciation + annual_interest


def energy_costs_perm3(
        energy_consumption_kwhperm3: float,
        energy_price_per_kwh: float):
    """
    Calculate the total energy costs per cubic meter.

    Parameters:
    energy_consumption_kwh (float): The total energy consumption in kWh.
    energy_price_per_kwh (float): The price of energy per kWh.

    Returns:
    float: The total energy costs.
    """
    return energy_consumption_kwhperm3 * energy_price_per_kwh


def energy_costs_peryear(
        energy_costs_per_m3: float,
        yearly_water_production_m3: float):
    """
    Calculate the total energy costs per year.

    Parameters:
    energy_costs_perm3 (float): The total energy costs per cubic meter.
    yearly_water_production_m3 (float): The yearly water production in cubic meters.

    Returns:
    float: The total energy costs per year.
    """
    return energy_costs_per_m3 * yearly_water_production_m3


def operation_maintenance_costs_peryear(
        construction_costs: float,
        oper_maintenance_percentage: float,
        ):
    """
    Calculate the annual operation and maintenance costs.

    Parameters:
    construction_costs (float): The total construction costs of the asset.
    oper_maintenance_percentage (float): The operation and maintenance costs as a 
        percentage of construction costs.

    Returns:
    float: The annual operation and maintenance costs.
    """
    return construction_costs * (oper_maintenance_percentage / 100)


def chemical_costs_peryear(
        chemical_usage_kgperm3: float,
        chemical_price_per_kg: float,
        yearly_water_production_m3: float,        
):
    """
    Calculate the total chemical costs per year.

    Parameters:
    chemical_usage_kgperm3 (float): The chemical usage in kg per cubic meter.
    chemical_price_per_kg (float): The price of chemicals per kg.
    yearly_water_production_m3 (float): The yearly water production in cubic meters.

    Returns:
    float: The total chemical costs per year.
    """
    chemical_costs_perm3 = chemical_usage_kgperm3 * chemical_price_per_kg
    return chemical_costs_perm3 * yearly_water_production_m3


def total_investment_costs_peryear(
        construction_costs_total: float,
        interest_rate: float,
        oper_maintenance_percentage: float,
        energy_costs_peryr: float,
        personnel_costs_peryr: float,
        chemical_costs_peryr: float = 0.0,
        lifespan_years: int = 30,
        ):
    """
    Calculate the total annual investment costs including interest, depreciation,
    and operation & maintenance costs.

    Parameters:
    construction_costs (float): The total construction costs of the asset.
    interest_rate (float): The annual interest rate (as a decimal).
    lifespan_years (int): The lifespan of the asset in years.
    oper_maintenance_percentage (float): The operation and maintenance costs as a 
        percentage of construction costs.

    Returns:
    float: The total annual investment costs.
    """
    interest_depreciation = interest_and_depreciation(
        construction_costs_total,  # plc costs are included in total
        interest_rate,
        lifespan_years)
    oper_maintenance_costs = operation_maintenance_costs_peryear(
        construction_costs_total,
        oper_maintenance_percentage)
    total_costs = (
        interest_depreciation +
        oper_maintenance_costs +
        energy_costs_peryr +
        personnel_costs_peryr +
        chemical_costs_peryr
        )
    return total_costs


def levelized_cost_of_water(
        total_investment_costs_peryear: float,
        yearly_water_production_m3: float):
    """
    Calculate the levelized cost of water (LCOW).

    Parameters:
    total_investment_costs_peryear (float): The total annual investment costs.
    yearly_water_production_m3 (float): The yearly water production in cubic meters.

    Returns:
    float: The levelized cost of water (LCOW) per cubic meter.
    """
    if yearly_water_production_m3 <= 0:
        raise ValueError("Yearly water production must be greater than zero.")
    lcow = total_investment_costs_peryear / yearly_water_production_m3
    return lcow
