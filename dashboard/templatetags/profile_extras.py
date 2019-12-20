from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def percent_date(value, arg):
    if timezone.now().date() >= arg:
        return 100
    else:
        total = arg - value
        used = timezone.now().date() - value
        fraction = used / total
        return fraction
