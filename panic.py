def detect_risk(text):
    text = text.lower()

    if "fire" in text or "flood" in text or "earthquake" in text:
        return {
            "risk": "high",
            "warning": "Danger nearby. Move to a safer area."
        }

    if "drive" in text or "go outside" in text:
        return {
            "risk": "medium",
            "warning": "Check surroundings before moving."
        }

    return {
        "risk": "low",
        "warning": "No immediate hazard detected."
    }