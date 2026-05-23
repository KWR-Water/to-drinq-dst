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
    if abs(val) >= 1000:
        return f"{val:,.1f}"
    else:
        return f"{val:.1f}"


register.filter('format_kpi_value', format_kpi_value)


@register.simple_tag
def scaled_kpi_display(value, kpi_name):
    """
    Return a display payload for KPI values, with optional cost scaling.

    Cost-related KPIs are scaled for readability when values become large:
    - >= 1,000,000 -> divided by 1,000,000 and unit prefix 'M'
    - >= 1,000 -> divided by 1,000 and unit prefix 'k'
    """
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return {
            "value": value,
            "unit_prefix": "",
        }

    kpi_label = str(kpi_name or "").lower()
    is_cost_kpi = "cost" in kpi_label

    if is_cost_kpi and abs(numeric_value) >= 1_000_000:
        return {
            "value": format_kpi_value(numeric_value / 1_000_000),
            "unit_prefix": "M",
        }

    if is_cost_kpi and abs(numeric_value) >= 1_000:
        return {
            "value": format_kpi_value(numeric_value / 1_000),
            "unit_prefix": "k",
        }

    return {
        "value": format_kpi_value(numeric_value),
        "unit_prefix": "",
    }
