def assess_emergency(text):
    text = text.lower()

    if "bleeding" in text or "unconscious" in text:
        return {
            "severity": "critical",
            "score": 0.9,
            "advice": "Apply pressure and seek immediate help"
        }

    elif "fire" in text or "flood" in text or "earthquake" in text:
        return {
            "severity": "high",
            "score": 0.8,
            "advice": "Move to a safer area immediately"
        }

    elif "pain" in text or "injury" in text:
        return {
            "severity": "high",
            "score": 0.7,
            "advice": "Stay still and monitor condition"
        }

    else:
        return {
            "severity": "low",
            "score": 0.3,
            "advice": "Monitor and stay safe"
        }