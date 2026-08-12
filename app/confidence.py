def calculate_confidence(level):
    levels = {'HIGH': 95, 'MEDIUM': 75, 'LOW': 45, 'UNVERIFIED': 20}
    return levels.get(level, 0)

# The weighted system would be in a full implementation; simplified here.