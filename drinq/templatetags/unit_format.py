import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def superscript_exponents(value: str) -> str:
    """
    Replace ^exponent patterns with HTML <sup>...</sup> for superscripts.
    Examples:
        m^3 -> m<sup>3</sup>
        10^-3 -> 10<sup>-3</sup>
    """
    if not isinstance(value, str):
        return value

    # Replace ^-??\d+ with <sup>...</sup>    
    def repl(match):
        return f"<sup>{match.group(1)}</sup>"
    # Handles both ^3 and ^-3
    result = re.sub(r'\^(\-?\d+)', repl, value)
    return mark_safe(result)

register.filter('superscript_exponents', superscript_exponents)
