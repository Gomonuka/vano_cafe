from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Retrieve the value of the given key from a dictionary."""
    return dictionary.get(key, 0)  # Default to 0 if the key doesn't exist
