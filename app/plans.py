def is_401k_plan(plan_name, plan_type_code=None):
    """Determine if plan is a 401(k)."""
    name_lower = plan_name.lower() if plan_name else ''
    keywords = ['401k', '401(k)', 'savings plan', 'retirement savings', 'employee savings',
                'profit sharing plan', 'defined contribution plan']
    for kw in keywords:
        if kw in name_lower:
            return True
    # If plan_type_code (from Form 5500) is available, use it
    # Typically 2E, 2J, etc. but not implemented here
    return False