# Design decisions

What was decided, one section per part of the app. The spike write-ups hold the
measurements these were taken from.

## Choosing what the app counts

A tracked word is an entry on the list the app counts: the undesirable
vocabulary someone has decided to drop.

- **The list holds whatever its author actually overuses**, ambiguous everyday
  words included.
- **Every occurrence is counted**, without weighing it against the sentence
  around it.
- **Entries may be more than one word.** The matcher takes the longest phrase
  that matches and consumes the words it used before looking for the next one.
- **One habit is counted under one name, with its other forms listed beside
  it.** A form is another way of saying the same word, so "vibe" gathers "vibes"
  and "vibing".
- **The list is editable in source and fixed at runtime.**
- **Every form earns its place by being spoken into the recognizer first.** A
  form the recognizer will not return counts 0 for the life of the app, while
  the matcher stays correct and every test passes.
- **Letting someone else build a list is deferred**, nothing yet catching a word
  the recognizer mishandles.

## Counting tracked words in a revising transcript

A segment is one stretch of transcript. The recognition task discards the
transcript it has been building and starts another on its own schedule, many
times within a single session.

- **A segment is counted once, at the rollover, from the text last seen before
  it.** So the count only ever goes up.
- **Stopping counts the segment in progress before it ends the session**, so the
  speech since the last rollover still reaches the totals. Anything the
  recognizer delivers after the stop is dropped.
- **A rollover is spotted by length: a transcript half the length of the one
  before it, or shorter, is a new segment.** The transcript can shrink for
  2 reasons. Just before discarding a segment the recognizer re-reads it with
  everything it heard and hands back a corrected version, which comes back at
  roughly the length it already had. A new segment starts from the first few
  words of new speech, so it is far shorter, and half separates the 2 cleanly.
- **The rollover check sits in its own tracker.** It keeps the previous
  transcript, compares each new one against it, and hands back a finished
  segment when the length drops. It sits between the code receiving recognition
  callbacks and the code counting words, which makes it plain text comparison
  that a test can run without a microphone.
- **A multi-word entry split across a rollover is missed, and that is
  accepted.** Each segment is counted on its own, so "to be" ending one segment
  and "honest" beginning the next matches nothing. No speech is lost at the
  boundary and both words still count toward the total spoken; only the phrase
  goes unrecognized, and only for entries of more than one word.

## Holding the totals of one session

A session is one stretch of listening, from the moment the app starts counting
to the moment the person speaking confirms a stop.

- **One object holds every number the interface shows**, and anything else is
  derived from them there.
- **The word count comes back from the same call that counts the tracked
  words**, so a single split of the text defines what a word is.
- **The measure of a habit is the percentage of spoken words that were tracked
  ones.**
- **Stopping freezes the elapsed time.**
- **A session that has counted nothing is distinguishable from one that has
  counted zero.** The interface says it is listening until the first segment
  lands.
- **Starting again discards what the last session counted.**

## Streaming speech from the microphone

Authorization is the system's record of whether this app may use the microphone
and may use speech recognition, held separately for each and changed by the
person in System Settings.

- **The pipeline owns the 4 Apple pieces that have to be alive together** — the audio engine, the tap copying its input, the recognition request, and the recognition task — which can only be started and stopped in one order.
- **Both authorization statuses are read before anything starts**, and an engine
  is started only when both are granted.
- **Recognition runs solely on device.** By default the framework sends audio to Apple's servers, where a recognition task ends by itself after about a minute, silently and with no error raised. On device no such limit applies, so one task covers the whole session, and the audio never leaves the Mac. The app will not run at all where on-device recognition is unavailable.
- **The microphone is released when a session stops.** The engine, its tap, the
  request and the task are built at start and torn down at stop, so an idle app
  shows no microphone indicator in the menu bar. A cancelled recognition task
  cannot be restarted, so keeping one alive between sessions would make every
  session after the first a silent one.
- **A refusal names the permission it is about**, the 2 being granted on
  separate System Settings panes.
- **A session ends when the microphone stops sending audio, and the app raises
  an alert.** The engine stops itself when the input device changes. Nothing in
  the framework says so, and a session left alone keeps running while it counts
  nothing. The app catches this by counting the buffers the tap delivers. A
  count that stands still means the audio stopped. The session ends there,
  keeping every word counted up to that moment.

## Showing one session in the menu bar

- **The interface holds no count of its own.** The menu (drop down with active counts and totals) is built from the session when it opens, the status item (the app's icon and count in the menu bar) is redrawn as each segment commits, and a menu left open during a running session re-reads every number once a second. A stopped session needs no redraw, its numbers having stopped changing.
- **The tracked words, their counts and the totals are the brightest text in the
  menu.** AppKit greys out any row that cannot be clicked, so each is drawn with
  its own view instead.
- **Every item is built to one width, settled before anything is drawn.** That
  holds the counts in a column and leaves room for the longest text an item will
  ever show.
- **Rows hold the tracked list's order while a session runs, and sort by count
  once it stops.** Words sharing a count keep the order the tracked list gives
  them.
- **A session ends when recognition reports an error.**
