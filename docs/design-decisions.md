# Design decisions

Decisions taken from the spike results. They are recorded here rather than
under any one spike, because each draws on more than one run, and the spike
sections above are meant to stay a record of what each run measured.

## Choosing what the app counts

Settled after [Spike 5](spike-5-long-session-continuity.md), and the reason the project is named for verbal habits
rather than for filler words. The app counts a list of tracked words: the
undesirable vocabulary someone has decided to drop, which the app exists to
make countable.

- **The list holds whatever its author actually overuses.** Whoever ships the
  app picks the words, and a tracked word does not have to be unambiguous.
  Most of what a person leans on is ordinary vocabulary — "just", "well",
  "stuff", "to be honest" — and that is exactly why the habit is hard to hear
  in your own speech and worth putting a number on.
- **Restricting the list to unambiguous words was considered and dropped.**
  [Spike 4](spike-4-filler-word-preservation.md) established that "um" and "uh" cannot be recovered from the
  recognizer at any level. Spike 5 then found roughly half the "like" instances
  in a minute of unscripted speech doing ordinary work. One reading of that
  measurement is to admit only words with no ordinary usage, which leaves slang
  and profanity and very little else. The reading taken here is that it names
  a cost to carry, because a list of unambiguous words omits nearly every word
  a speaker would want to work on.
- **Every occurrence is counted.** Weighing each occurrence against the
  sentence around it is separate work that nothing else depends on and can be
  added later.
- **Entries may be more than one word.** Phrases like "to be honest" are real
  entries, so the matcher takes the longest phrase that matches and consumes
  the words it used before looking for the next one. Against a list holding
  only single words this behaves identically, which makes the capability free
  to keep.
- **The list is editable where it is written and fixed where it is used.**
  Editing it in source is how the list changes, which makes it configuration
  without an interface having to be built for it. Anyone running what was
  shipped gets the list as shipped. This closes the question Spike 4 deferred,
  of whether the list is a fixed default, user-configurable, or both: the
  curated default comes first, because it is the least that proves the matching
  pipeline end to end, and supplying words some other way changes only where
  they come from.
- **Letting someone else build a list is deferred.** A word the recognizer
  mishandles counts zero for the life of the app with nothing indicating why.
  The check that catches this works because the person choosing the words is
  the person running it, so any interface for adding words needs its own
  answer — a warning at entry, or a recognizer test built in.

## Counting tracked words in a revising transcript

Settled after [Spike 6](spike-6-on-device-recognition.md), replacing the stable-prefix design that Spike 6
disproved. This answers both of the decisions Spike 6 deferred: whether to
count live and correct afterwards, and where the check for a rollover belongs.
It also answers Spike 5's question about the shape of the matcher's reset.

- **A segment is counted once, after the recognizer is finished with it.**
  Nothing is counted while a segment is still being revised. When the
  transcript rolls over, whatever text was last seen before the rollover is
  taken as final: count its tracked words and its total words, add both to the
  session totals, then start tracking the new transcript. Stopping the session
  counts the segment still in progress, or the last stretch of speech is lost.
- **Waiting for the rollover was chosen over counting live and correcting
  afterwards.** Waiting up to ~45s for a segment to roll over does not put the
  displayed count 45s behind the speech. Every segment that has already rolled
  over is fully counted; the only words missing are the ones spoken since the
  current segment began. Spike 5 logged words from the tracked list arriving
  about five times a minute, and Spike 6's segments averaged about 23s, so
  roughly two tracked words are waiting to be counted at any given moment.
  Counting live recovers those two, but any already-counted word that a
  close-out pass rewrites then has to come back out of the displayed count,
  and Spike 6 logged nine close-outs in five minutes, each changing words.
  Waiting means every number added to the count has already stopped changing,
  so the count only ever goes up.
- **The count is taken at the rollover.** The close-out pass is the more
  obvious place to take it, since it is the recognizer's last look at the
  segment, but it does not happen every time — only nine of the thirteen
  rollovers in Spike 6's on-device run had one in front of them. Counting at
  the close-out would silently skip the other four segments. Every segment
  ends in a rollover, so that is the one place a count can be taken reliably.
  Where a close-out did happen, its corrections are already in the text the
  rollover hands over.
- **A rollover is recognized by the drop in length.** Checking only whether
  the new transcript stopped extending the old one is not enough, because a
  close-out revision also stops extending it, and counting a close-out as a
  rollover would count the same segment twice. The size of the drop separates
  them: a close-out rewrites the segment at roughly the same length, while a
  rollover replaces it with something far shorter. In Spike 6's on-device run
  a 448-character transcript was replaced by `OK` 0.00s later.
- **The rollover check sits in its own small tracker**, between the code that
  receives recognition callbacks and the code that counts words. The tracker
  holds the previous transcript and hands out finished segments. Counting is
  then a plain function of one segment's text, and the running session totals
  live somewhere else again. This keeps text comparison out of the audio
  pipeline, which cannot be tested without a microphone.
- **The drop is measured as a fraction of the previous transcript, and half is
  the line.** A new transcript at half the length of the one before it, or
  shorter, is a rollover; anything longer than that is the same segment being
  rewritten. The number is a midpoint rather than a tuned threshold, because
  the two behaviours it separates sit far apart on either side of it. The one
  rollover measured in full collapsed a 448-character transcript to two
  characters, under half a percent, and a close-out rewrites a segment within a
  few percent of the length it already had. Anywhere between those would
  classify both correctly, so the midpoint was taken and the measurement
  written down beside it. A future run that logs a rollover into a long first
  utterance is what would move it.
- **A tracked word spoken across a rollover is missed, and that is accepted.**
  Each segment is counted whole and on its own, so an entry of more than one
  word that begins in one segment and finishes in the next matches neither
  half: "to be" ending a segment and "honest" beginning the following one
  counts as no occurrence of "to be honest". Carrying the tail of a segment
  forward to be reconsidered against the next one would recover it, at the cost
  of the property that makes the count trustworthy, which is that a segment is
  read exactly once and never revisited. Segments run twelve to forty-five
  seconds and multi-word entries take under a second to say, so the boundary
  landing inside one is rare. The acceptance is recorded here so that a later
  reader takes it for a limit of the design rather than a bug in it.
