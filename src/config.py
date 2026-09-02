"""The vocabulary the app counts. Editing this file is how the list changes.

Each key is the name a habit is counted under, and the value holds the other
forms counted toward it. Names and forms are lowercase and may be more than one
word. Matching takes the longest form that fits before looking for the next one,
so a phrase and a word inside it can both appear here.

Each form here has been spoken into the recognizer and its output read back.

docs/design-decisions.md carries the reasoning behind this design.
"""

TRACKED_WORDS = {
    "bro": (),
    "vibe": (
        "vibes",
        "vibing",
    ),
    "to be honest": (),
    "well": (),
    "stuff": (),
    "fuck": (
        "fucking",
        "fucked",
        "fucker",
        "motherfucker",
        "fucks",
    ),
    "just": (),
    "stupid": (
        "stupidest",
        "stupidly",
    ),
}
