import json

def text_match(text, countries):
    text = text.lower()
    for c in countries:
        if c.name.lower() in text:
            return c
    return None
