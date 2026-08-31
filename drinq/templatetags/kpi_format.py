from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def adaptability_symbol(score):
    """Map adaptability score to symbol and color class."""
    try:
        val = float(score)
    except (TypeError, ValueError):
        return ('?', 'text-muted')
    # Use a tolerance for float comparison
    if abs(val - 1.0) < 0.01:
        return ('+', 'text-success fw-bold')
    if abs(val - 0.75) < 0.01:
        return ('0/+', 'text-primary fw-bold')
    if abs(val - 0.5) < 0.01:
        return ('0', 'text-secondary fw-bold')
    if abs(val - 0.0) < 0.01:
        return ('-', 'text-danger fw-bold')
    # fallback: show value
    return (f"{val:.2f}", 'text-muted')


@register.filter
def adaptability_symbol_html(score):
    symbol, css = adaptability_symbol(score)
    return mark_safe(f'<span class="{css}">{symbol}</span>')


def format_decimals(value):
    """
    Format a numeric value for display with a sensible decimal precision:
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


register.filter('format_decimals', format_decimals)


def format_parameter_value(value):
    """Format technology and water-quality parameter values by magnitude.

    Rules:
    - 4 decimals for |value| < 0.01
    - 3 decimals for |value| < 1
    - 2 decimals for 1 <= |value| < 10
    - 1 decimal for 10 <= |value| < 100
    - 0 decimals for |value| >= 100
    """
    try:
        val = float(value)
    except (TypeError, ValueError):
        return value

    abs_val = abs(val)
    if abs_val < 0.01:
        return f"{val:.4f}"
    if abs_val < 1:
        return f"{val:.3f}"
    if abs_val < 10:
        return f"{val:.2f}"
    if abs_val < 100:
        return f"{val:.1f}"
    return f"{val:.0f}"


register.filter('format_parameter_value', format_parameter_value)


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
            "value": format_decimals(numeric_value / 1_000_000),
            "unit_prefix": "M",
        }

    if is_cost_kpi and abs(numeric_value) >= 1_000:
        return {
            "value": format_decimals(numeric_value / 1_000),
            "unit_prefix": "k",
        }

    return {
        "value": format_decimals(numeric_value),
        "unit_prefix": "",
    }
