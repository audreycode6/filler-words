"""The vocabulary the app counts. Editing this file is how the list changes.

Entries are lowercase and may be more than one word. Matching takes the longest
entry that fits before looking for the next one, so a phrase and a word inside
it can both appear here.

Each entry here has been spoken into the recognizer and its output read back.
An entry the recognizer mishandles counts 0 for the life of the app,
while the matcher stays correct and every test passes.
"""

TRACKED_WORDS = (
    "bro",
    "vibe",
    "to be honest",
    "well",
    "stuff",
    "fuck",
    "just",
    "stupid",
)
