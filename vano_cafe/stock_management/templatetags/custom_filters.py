from django import template

register = template.Library()
@register.filter
def get_item(dictionary, key):
    """Retrieves the value of the given key from a dictionary."""
    return dictionary.get(key, 0) 
