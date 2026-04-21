from django import template

register = template.Library()


def format_kpi_value(value):
    """
    Format a float value for KPI display:
    - 3 decimals if abs(value) < 1
    - 1 decimal if abs(value) >= 1
    Handles None and non-numeric gracefully.
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        return value
    if abs(val) < 1:
        if val == 0:
            return "0"
        return f"{val:.3f}"
    else:
        return f"{val:.1f}"


register.filter('format_kpi_value', format_kpi_value)
