"""One session's totals, and the place the interface reads them from.

A session is one stretch of listening: it starts, takes the count of each
segment as the recognizer finishes with it, and stops. It holds the per-entry
counts, the number of words spoken, how many segments have been counted, and
how long it has been running. Everything the menu shows is one of those or is
derived here from them, the percentage included.

This module is handed what `matcher.py`'s `count_tracked` returned and works
only on those numbers.
"""

import time


class Session:
    """The totals for one stretch of listening.

    The clock is taken as an argument so a test can move time by hand.
    """

    def __init__(self, tracked_words, clock=time.monotonic):
        self._clock = clock
        self._tracked_words = tuple(tracked_words)

        self.is_active = False
        self.counts = {entry: 0 for entry in self._tracked_words}
        self.total_word_count = 0
        self.segments_counted = 0

        self._started_at = None
        self._elapsed_at_stop = 0.0

    def start(self):
        """Begin a fresh session, discarding whatever the last one counted.

        Every tracked entry is present at 0 from this moment.
        """
        self.is_active = True
        self.counts = {entry: 0 for entry in self._tracked_words}
        self.total_word_count = 0
        self.segments_counted = 0

        self._started_at = self._clock()
        self._elapsed_at_stop = 0.0

    def record(self, counts, word_count):
        """Fold one committed segment's counts into the totals.

        Takes what `count_tracked` returned. A segment arriving after the stop
        is dropped.
        """
        if not self.is_active:
            return

        for entry, count in counts.items():
            self.counts[entry] = self.counts.get(entry, 0) + count
        self.total_word_count += word_count
        self.segments_counted += 1

    def stop(self):
        """End the session, holding the elapsed time where it stands."""
        if not self.is_active:
            return

        self._elapsed_at_stop = self.elapsed_seconds
        self.is_active = False

    @property
    def total_tracked_count(self):
        """How many tracked words were said, across every entry."""
        return sum(self.counts.values())

    @property
    def elapsed_seconds(self):
        """How long the session has been running, frozen once it stops."""
        if not self.is_active:
            return self._elapsed_at_stop

        return self._clock() - self._started_at

    @property
    def tracked_percentage(self):
        """What percentage of the words spoken were tracked ones.

        A session that has heard no words yet is at zero.
        """
        spoken = self.total_word_count
        if spoken <= 0:
            return 0.0

        return self.total_tracked_count / spoken * 100
