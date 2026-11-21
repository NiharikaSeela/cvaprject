"""
Small helpers for turning raw class names and counts into readable text.
Kept separate so both the monitoring and PUB modules can use them.
"""
import config


def display_name(class_name: str) -> str:
    return config.DISPLAY_NAMES.get(class_name, class_name)


def is_alert_class(class_name: str) -> bool:
    return class_name in config.ALERT_CLASSES


def level_for(count: int) -> str:
    if count >= config.HIGH_LEVEL_THRESHOLD:
        return "High"
    if count >= config.MODERATE_LEVEL_THRESHOLD:
        return "Moderate"
    return "Low"


def describe_issue(class_name: str, count: int) -> str:
    """Example: 'High Plastic levels'."""
    return f"{level_for(count)} {display_name(class_name)} levels"
