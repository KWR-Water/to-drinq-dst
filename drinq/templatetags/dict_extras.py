from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Returns the value for a given key from a dictionary."""
    return d.get(key)
