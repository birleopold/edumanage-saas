"""
Template tags for campus-aware UI components.
"""
from django import template

register = template.Library()


@register.inclusion_tag('components/campus_badge.html')
def campus_badge(campus, show_all_text=False):
    """
    Render a campus badge component.
    
    Usage:
        {% load campus_tags %}
        {% campus_badge student.campus %}
        {% campus_badge offering.campus show_all_text=True %}
    """
    return {
        'campus': campus,
        'show_all_text': show_all_text,
    }


@register.inclusion_tag('components/campus_filter.html')
def campus_filter(campuses, selected_campus_id, form_id='campus-filter'):
    """
    Render a campus filter dropdown component.
    
    Usage:
        {% load campus_tags %}
        {% campus_filter campuses selected_campus_id %}
    """
    return {
        'campuses': campuses,
        'selected_campus_id': selected_campus_id,
        'form_id': form_id,
    }


@register.inclusion_tag('components/campus_indicator.html')
def campus_indicator(campus):
    """
    Render a campus indicator for page headers.
    
    Usage:
        {% load campus_tags %}
        {% campus_indicator current_campus %}
    """
    return {
        'campus': campus,
    }


@register.filter
def campus_display(campus):
    """
    Format campus for display.
    
    Usage:
        {{ student.campus|campus_display }}
    """
    if campus:
        return campus.name
    return "No campus assigned"


@register.filter
def campus_class(campus):
    """
    Get CSS class for campus badge.
    
    Usage:
        <span class="campus-badge {{ campus|campus_class }}">
    """
    if not campus:
        return "campus-all"
    if getattr(campus, 'is_default', False):
        return "campus-primary"
    return ""
