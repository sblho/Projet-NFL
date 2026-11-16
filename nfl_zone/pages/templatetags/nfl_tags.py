from django import template
from pages.models import LiveMatchBanner

register = template.Library()


@register.inclusion_tag("pages/includes/live_match_banner.html")
def live_match_banner():
    banner = LiveMatchBanner.objects.filter(is_active=True).first()
    return {"banner": banner}