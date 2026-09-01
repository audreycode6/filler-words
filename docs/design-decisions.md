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
- **One habit is counted under one name, with its other forms listed beside
  it.** A form is another way of saying the same word — "vibe" gathering
  "vibes" and "vibing". So the list maps a name to its other forms, and
  the counts come back keyed by the name, giving the menu one row for the
  habit. Which forms belong to a habit is a choice about vocabulary, made by
  whoever edits the list.
- **The list is editable where it is written and fixed where it is used.**
  Editing it in source is how the list changes, which makes it configuration
  without an interface having to be built for it. Anyone running what was
  shipped gets the list as shipped. This closes the question Spike 4 deferred,
  of whether the list is a fixed default, user-configurable, or both: the
  curated default comes first, because it is the least that proves the matching
  pipeline end to end, and supplying words some other way changes only where
  they come from.
- **Every form earns its place by being spoken into the recognizer.** A word the
  recognizer will not return counts 0 for the life of the app, while the matcher
  stays correct and every test passes. Nothing exposes which words the model
  holds, so speaking one is the only way to find out: `python src/audio.py`
  prints what came back for each, and the running app shows whether the count
  moves.
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

## Holding the totals of one session

A session is one stretch of listening, from the moment the app starts counting
to the moment the person speaking confirms a stop. These decide what a session
holds and what is derived from it, so that the numbers on screen have exactly
one definition each.

- **One object holds every number the interface shows.** The per-entry counts,
  the words spoken, how many segments have been counted and how long the
  session has run all live together, and anything else is derived from them
  there. The alternative is an interface that keeps a tally of its own — a
  number held by the status item's title, or by a menu row, raised by 1 each
  time a segment arrives. That number is a second copy of the count, correct
  only for as long as every update reaches it. An open menu puts the app into
  an event-tracking mode where work scheduled the ordinary way stops running
  until the menu closes, and a session started again sets the stored counts
  back to 0 while the held number keeps whatever it last showed. Reading every
  number off the session each time the menu opens leaves nothing that can fall
  behind.
- **The word count comes back from the call that counts the tracked words.**
  Both numbers need the segment split into words first, and that split is where
  the definition of a word lives: whether a trailing comma is part of one,
  whether "watermelon's" is one word or two. Counting the words anywhere else
  means splitting the text a second time against a second definition, and two
  definitions that disagree by a little put a number on screen that is wrong by
  a little, which is the hardest kind to notice. Both numbers come back from
  one split, and the session adds them up.
- **The measure of a habit is the percentage of spoken words that were tracked
  ones.** 12 of them in 200 words and 12 in 2000 are different habits, and a
  total on its own cannot tell them apart. What carries that difference is how
  much was said, which the session already counts as each segment commits. A
  percentage moves only when a segment commits, and cannot exceed the count it
  is drawn from. It is derived where the counts live rather than worked out
  when a menu opens, so it cannot come out differently in 2 places that show
  it.
- **Stopping freezes the elapsed time.** A stopped session stays on screen as
  its summary, and a duration climbing inside a summary reads as a live number.
  What the person is reading must not move underneath them. Anything in flight
  is counted before the stop or not at all.
- **A session that has counted nothing is distinguishable from one that has
  counted zero.** A segment takes 12 to 45 seconds to commit, so
  every session has nothing to show for its first stretch. A denied
  microphone produces silent audio and an empty transcript, which counts 0
  for as long as it runs, so a bare 0 on screen has two very different
  meanings. Counting the committed segments separates them, and the interface
  can say it is listening until the first one lands.
- **Starting again discards what the last session counted.** Nothing is kept
  between sessions. Keeping a history is separate work.

## Streaming speech from the microphone

Settled after [Spike 6](spike-6-on-device-recognition.md), drawing on the runs
before it. One object, the pipeline, owns the 4 Apple pieces that have to be
alive together — the audio engine, the tap that copies its input, the
recognition request the audio is fed to, and the recognition task that returns
text — because they can only be started and stopped in one order.

- **Authorization is read before anything starts.** Authorization is the
  system's record of whether this app may use the microphone and may use speech
  recognition, held separately for each and changed by the person in System
  Settings. [Spike 1](spike-1-mic-permission.md) found that a denied microphone
  raises nothing: the engine starts, reports success, and delivers buffers of
  zeros for as long as it runs. Both statuses are therefore read up front, and
  an engine is started only when both are granted.
- **The two statuses are mapped separately.** The frameworks number them
  differently: for the microphone 1 is restricted and 2 is denied, and for
  speech recognition they are reversed. Reading one with the other's ordering
  turns a refusal the person can lift into one they cannot. Each ordering is
  written down on its own, and when the two disagree the one that blocks is
  what gets reported, since listening needs both.
- **Recognition runs on device, and a machine that cannot do it stops rather
  than falling back.** Falling back to Apple's servers is what the framework
  does when left alone, so refusing it is the decision, and the cost is that
  the app will not run at all on a machine without on-device support. That is
  accepted because [Spike 5](spike-5-long-session-continuity.md) measured the
  server path ending by itself after about a minute with no error raised, which
  would count the opening minute of a session and discard the rest.
- **Nothing holds the microphone between sessions.** The recognition request
  and the task are built when listening starts and released when it stops, so
  an app sitting idle in the menu bar leaves no microphone indicator showing. A
  cancelled task cannot be restarted in any case, so holding one across
  sessions would make every session after the first a silent one.
- **A refusal names the permission it is about.** The microphone and speech
  recognition are granted on separate System Settings panes, so a message
  covering both sends someone to a pane showing a permission already allowed,
  which reads as the app being broken. The 2 states are already known where
  they are reduced to the 1 the app acts on, so they are carried through and
  only the ones actually in that state are named.

## Showing one session in the menu bar

Settled after [Spike 3](spike-3-thread-safety.md). The status item and its
dropdown are the whole interface. 5 things are decided here that reading the
code will not tell you.

- **The interface holds no count of its own.** A number kept in the interface
  is a second copy of the count, correct only for as long as every update
  reaches it. Every number is re-read from the session instead: as the menu
  opens, and again on each refresh while it stays open, so the menu and the
  status item beside it always agree. An open menu puts the app into an
  event-tracking mode, so the redraw is dispatched to the main queue, which
  keeps delivering through that mode. Elapsed time moves between committed
  segments while every other number waits for one, so a timer registered in
  the common run loop modes redraws the open menu once a second.
  The menu's structure is settled the moment it opens — every event that would
  add, remove or reorder an item closes the menu to happen — so a redraw writes
  text into items that are already there and never touches the list itself.
- **The numbers draw brightest, which takes a view for every item.** The
  counts, the totals and the percentage are what the menu is opened to read, so
  they take the strongest text color the system offers and the header above
  them steps back. AppKit dims the title of any item that cannot be clicked, so
  each of these is drawn by a view of its own to escape that. Start and Quit
  are left as the system draws them, and a refusal's explanation is muted along
  with its header.

  Nothing sizes a menu around a view, so the width is settled before anything
  is built — the widest word plus a column for its count, or the longest of the
  lines below the rows — and every item is built to it. That holds the counts
  in a column and stops the menu widening as the elapsed time grows a digit. A
  sentence wraps rather than widening it further, and counts are set in a
  monospaced-digit font.

- **Rows hold the tracked list's order while a session runs, and sort by count
  once it stops.** A row that moves while it is being read is the thing to
  avoid, and during a session the counts change under the reader; afterwards
  they cannot. So the running order is fixed and the summary is ranked, which
  is the order worth having when the numbers are final. Words sharing a count
  are left in the order the tracked list gives them, since the count alone
  cannot say which of 2 words on 5 comes first. Otherwise 2 sessions ending on
  the same counts could list those words differently, and the rows would look
  shuffled for no visible reason.
- **A refusal is worded for whoever holds the permission.** macOS grants a
  permission to the responsible process, which is the application that launched
  the code rather than the code itself. Run from a source checkout, the entry
  in the settings pane carries the name of the terminal or editor the launch
  came from, so a message naming this app sends the reader hunting for a row
  that the pane does not hold. The wording therefore asks for the permission to
  be turned on for whichever application ran it. Packaged as its own signed
  application, this app becomes the responsible process, the pane carries its
  name, and the message names it. The 2 wordings are chosen by asking whether
  the main bundle belongs to this app, which is a question with an answer in
  every launch. Public interfaces cannot report the responsible process from
  inside the process, and the parent of a running interpreter is often a helper
  that belongs to no application at all.

  [Spike 2](spike-2-stt-streaming.md) records the sharper edge of the same
  attribution. Speech authorization raises a TCC error and takes the process
  down when the responsible application lacks
  `NSSpeechRecognitionUsageDescription`, which is why the recognizer runs from
  Terminal and stops under editors missing that key. No message can cover it,
  since nothing survives to draw one.

- **A session ends when recognition reports an error.** Speech arriving while
  recognition is failing goes uncounted, and a total short by an unknown amount
  reads as a habit improving, which can mislead the person using it.
  Ending the session ensures every session on screen counted
  continuously from its start to its stop. The status item drops
  its count for a warning symbol at the same moment.
  Each error is written to the log with its domain and code, which is
  what will say how often that happens. The stop cancels the
  recognition task, and the error a cancelled task reports is dropped at the
  number it was started under, so it cannot land on the session started next.
