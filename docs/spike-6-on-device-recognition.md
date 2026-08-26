# Spike 6: On-Device Recognition & Revision Locality

Script: [`spikes/spike6_on_device_recognition.py`](../spikes/spike6_on_device_recognition.py)


**Question:** Two questions [Spike 5](spike-5-long-session-continuity.md) left open. Does the ~60s recognition-task
cap survive `requiresOnDeviceRecognition = True`? And are partial-result
revisions confined to the tail of the transcript, as stable-prefix counting
assumes? Spike 5 could not answer the second: its log truncated to the last 45
characters, so the front of the transcript was never observed.

**Method:** Spike 5's script copied to `spike6_on_device_recognition.py` and
extended in three ways, keeping the two-counter design (buffers in, callbacks
out) intact:

1. `ON_DEVICE` / `DURATION` module constants. On-device prints
   `supportsOnDeviceRecognition()` and sets
   `setRequiresOnDeviceRecognition_(True)`, then prints the request's actual
   flag back. If on-device is requested but unsupported the script aborts
   rather than falling back to the server, so a server run can never be
   mistaken for an on-device one.
2. The full transcript logged every callback instead of `text[-45:]`, plus a
   `find_revision(previous, current)` helper that returns `None` when
   `current` extends `previous` and otherwise reports how far behind the old
   tail the recognizer rewrote, in characters and in words. Running maxima go
   in the `SUMMARY`.
3. A fixed `PASSAGE` read aloud at the start, seeded with "like" as filler and
   as verb, plus "so", "um" and "uh".

A `--selftest` flag checks `find_revision` against seven synthetic cases
without touching the mic. It caught a real bug before the run: a divergence
landing on a space counted the preceding word as rewritten even when it was
intact, inflating `max_words_back`.

Two runs: 300 seconds on-device, reading the passage and then talking
continuously; then 120 seconds with `ON_DEVICE = False`, reading the same
passage once. The transcripts are diffed against the passage word-for-word,
after lowercasing and stripping punctuation.

**Result:**

The ~60 second cap does not apply on-device.

```
SUMMARY [ON-DEVICE]: ran 300.2s | buffers=3000 | callbacks=768
         last callback at +299.36s
         isFinal never fired
         revisions=77 max_chars_back=521 max_words_back=97
```

Against Spike 5's server-based run on the same script skeleton: callbacks
froze at 141, last at +61.54s, `isFinal=True`. Here recognition produced
callbacks for the entire five minutes, `isFinal` never fired once, and memory
stayed flat at 32.8MB → 33.2MB with recognition actually working the whole
time.

But the transcript is not one growing string. It resets to empty roughly
every 12-45 seconds, thirteen times across the run, with no `isFinal` and no
other signal. Ten of them, with the first word of the new segment:

```
+ 17.10s -> 'I like'      + 143.21s -> 'OK'
+ 51.36s -> 'So'          + 169.39s -> "We're"
+ 69.00s -> 'Where'       + 199.20s -> 'Fire'
+106.46s -> 'The'         + 211.54s -> 'Staying'
                          + 243.45s -> 'My'
                          + 287.78s -> 'You'
```

And revisions are not tail-local. Of 77 flagged revisions, 64 are ordinary
within-segment rewrites and 13 are resets — the ten above plus three that
were not tabulated separately. Thirteen is what the depth tables require:
they do not reconcile at any other number. The 64 split cleanly:

```
depth          count
1 word back       27
2 words           18
3 words            4
4 words            3
6 words            3
10+ words          9   <- the finding
```

The nine deep ones are the finding:

```
+  17.00s  char  108    64 chars /  12 words back
+  51.32s  char  106   323 chars /  60 words back
+  68.98s  char   18   257 chars /  52 words back
+ 106.41s  char    1   439 chars /  86 words back
+ 143.21s  char   54   448 chars /  84 words back
+ 169.28s  char   60   315 chars /  65 words back
+ 198.42s  char    1   341 chars /  67 words back
+ 243.38s  char   77   323 chars /  59 words back
+ 287.62s  char   27   501 chars /  89 words back
```

Every one of the nine is followed by a segment reset within 0.8 seconds, and
eight of the nine within 0.2. The correlation is 9 out of 9 in that
direction, but not in reverse: thirteen resets against nine deep revisions
means four segments rolled over with no close-out pass at all. A
representative pair, at +143.21s:

```
was: "it depends on the transcript staying put once it has been ridden I like
      the idea of county words as they settle rather than waiting for the end
      it works like a ratchet we're nothing behind the cursor ever moved again
      ... past the 6 second mark with speech still in progress"
now: "a depends on the transcript staying put once it has been written I like
      the idea of counting words as they said or rather than waiting for the
      end it works like a ratchet where nothing behind the cursor ever moves
      again ... past the 6 second mark with speech still in progress"
```

then, 0.00s later, the transcript is `'OK'`.

The server run reproduced Spike 5 exactly and answered the accuracy question:

```
SUMMARY [SERVER]: ran 120.2s | buffers=1200 | callbacks=174
         last callback at +61.30s
         first isFinal at +61.30s
         revisions=40 max_chars_back=692 max_words_back=135
```

Dead at +61.30s via `isFinal`, silently, with audio still flowing — the third
independent confirmation of the cap on the server path.

Word accuracy on the passage, 110 reference words. WER is word error
rate — the share of reference words the recognizer got wrong:

```
            word errors     WER
Server                9    8.2%
On-device            11   10.0%
```

The errors barely overlap. Both dropped "um" and "uh" and contracted "I am" →
"I'm". Beyond that, server missed `where` → `we're`, `past` → `pass`, `sixty
second` → `62nd`, `with` → `the`; on-device missed `past this point` →
`passes`, `the sixty` → `60`, `speech` → `with speed`, but got `where` right
where the server did not. **All three instances of "like" survived intact in
both.**

And the revision depths, which is where the two paths differ most:

```
depth          on-device (77 revs)   server (40 revs)
1-2 words                       47                 11
3-9 words                       11                  7
10-49 words                      3                 15
50+ words                       16                  7
max depth                       97                135
```

The server never resets — one continuous 787-character transcript for its
whole 61-second life. But it oscillates. A single word at character 93 flips
`as` ↔ `is` (and `ridden` ↔ `written`) at least nine times across the run,
and each flip re-emits everything downstream as changed.

**Interpretation:**

- **`requiresOnDeviceRecognition` removes the ~60s cap.**
  A single task ran the full five minutes and `isFinal` never
  fired, where the server-based Spike 5 task died silently at +61.54s.
  _This retires the two requirements Spike 5 created: the pipeline no longer
  has to recycle the request and task transparently mid-session, and the
  matcher no longer needs a per-task reset._ The "audio processed on-device
  only" NFR is satisfied by the same flag, for free.
- **The 60s problem was replaced, not eliminated.** The task survives, but
  the transcript still rolls over about every 12-45 seconds. The difference
  is that this rollover is _worse_ to detect than Spike 5's was: Spike 5 at
  least announced its death with `isFinal=True`. Here there is no signal at
  all. The only way to know a segment ended is to notice the transcript no
  longer extends what came before. _This is the fourth silent-failure mode
  in this stack_, after [Spike 1](spike-1-mic-permission.md)'s silent permission denial, [Spike 2](spike-2-stt-streaming.md)'s
  silently dropped streaming results, and Spike 5's silent task termination.
  The pipeline still needs to handle rollover; it just handles it by
  watching the text instead of watching `isFinal`.
- **Revisions are NOT confined to the tail.** Nine revisions reached
  12 to 89 words behind the tail. Stable-prefix counting assumes the
  recognizer never rewrites words from five seconds ago; it rewrote words
  from ninety seconds ago, repeatedly, in a single five-minute
  session.
- **But the deep revisions have a shape, and the shape is exploitable.**
  They are not scattered. Every deep revision is the recognizer's close-out
  pass on a segment: a full re-decode of everything it is about to discard,
  immediately before discarding it. _The converse does not hold_ — four of
  the thirteen rolls had no deep revision in front of them, so a matcher
  cannot treat a close-out as the signal that a roll is coming; it can only
  treat a roll as the thing it must re-count after. Within a segment, 64 of
  64 revisions stay
  within 6 words of the tail, and 45 of those are within 2. _So there are two
  regimes, not one._ A tail-local regime that holds for the life of a
  segment, and a single whole-segment rewrite at the boundary. A matcher that
  counted on the stable prefix during a segment and re-counted the segment
  once at its close-out would be correct, where one that counted a rolling
  prefix and never looked back would not.
- **Tail-locality fails on the server path too, and worse.** This is the
  result that matters most for the matcher, and it was not anticipated.
  Switching back to server recognition is not an escape from the problem: the
  server reached 135 words back where on-device reached 97, and 22 of its 40
  revisions went 10+ words back against 19 of on-device's 77. _The
  stable-prefix assumption is broken by `SFSpeechRecognizer` generally, not by
  on-device recognition specifically._
- **The two paths break it in different shapes.** On-device is quiet then
  loud: 47 of 77 revisions move 1-2 words, punctuated by one whole-segment
  rewrite every 12-45 seconds. The server is continuously unstable at one
  point: an early word oscillates for the entire life of the transcript, so
  no prefix is ever safe, at any time, at any depth. _On-device's failure is
  schedulable; the server's is not._ A matcher can wait for a close-out. It
  cannot wait for an oscillation that never settles.
- **Accuracy is comparable, and the gap does not favour either path
  meaningfully.** 8.2% WER server against 10.0% on-device, a difference of two
  words in 110, with errors that barely overlap — each path got right what the
  other got wrong. _On-device costs roughly nothing in accuracy._ Combined
  with the cap result and the NFR, on-device is the clear choice.
- **The close-out pass materially changes words, so it cannot be ignored.**
  "county words" → "counting words", "we're nothing" → "where nothing",
  "pass this point" → "past this point", "importing finding" → "important
  finding", "wanna know" → "one note". These are not cosmetic. A count taken
  before the close-out and a count taken after it are counts of different
  text.

> [!NOTE]
> **_Side findings (not this spike's question)_**
>
> - Unscripted on-device speech degrades noticeably worse than the read
>   passage: "assumption" → "Asuncion", "reading" → "raining", "accent" →
>   "accident", "settle" → "subtle". The 10.0% WER above is measured on
>   careful reading and should be read as a floor, not a typical case.
>
> **_Instrument caveat_**
>
> `find_revision` reports the distance from the first changed character to the
> end of the old text, not the number of words that actually changed. When the
> server flips `as` ↔ `is` at character 93 of a 787-character transcript, one
> word changed but the metric reports 135 words back. _The depth is accurate
> and is what stable-prefix counting cares about — a change at word 20 means
> the prefix was not stable — but the magnitude is overstated._ A future
> version should report both.

**Deferred Decisions:**

- How the pipeline detects a segment rollover. The mechanism is now known
  (the transcript stops extending), but where that check lives — matcher,
  pipeline, or a layer between — is design work, deliberately not settled
  here.
- Whether the matcher counts twice (once live, once at close-out) or defers
  counting a segment until its close-out lands. The first gives responsive
  UI with a correction; the second gives a stable count with up to ~45s of
  lag. This is the decision the stable-prefix design now has to be rebuilt
  around.

_Both deferred decisions above are settled. The mechanism that replaced
stable-prefix counting is recorded under **Design decisions** at the end of
this file._

**Question Moving Forward:**

- Does the segment length vary with speech rate, silence, or content?
  Thirteen resets over five minutes, and the ten logged ranged from ~12s to
  ~45s apart, with no evident cause. This matters because a filler word is
  counted only when its segment rolls over, so the wait before it appears in
  the count is however long that segment has left to run. If segments have a
  maximum length, the longest that wait can ever be is known too. One
  five-minute run shows the range that happened to occur, which is not the
  same as a limit.
- Does the close-out pass ever cross a segment boundary — can text from two
  segments ago change? This is the one observation that would break counting
  by segment. That text has already been counted, so a change to it could only
  be corrected by taking the count back down. Nothing observed suggests it
  happens, but this run did not test it directly.
- A separate question, about the segment still open rather than the ones
  already counted: can a segment be re-decoded more than once before it rolls
  over? Counting by segment absorbs this either way, since only the last text
  before the rollover is counted, however many times it was rewritten first.
  Worth knowing, but nothing in the design depends on the answer.
- Does the on-device path ever oscillate the way the server does — an early
  word flipping repeatedly within a live segment? Nothing in this run shows
  it, and the 1-2 word depth of 47 of 77 revisions argues against it. This
  mattered while the matcher counted from the live prefix. Counting by segment
  never reads a segment until it is finished, so an early word flipping inside
  an open segment is invisible to it.

**Status:** Spike complete, all three questions answered.

**The cap:** gone on-device. Recognition ran 300 seconds without a single
`isFinal`, where the server path died at 61.30s — the third confirmation of
that cap. Running on-device therefore removes the need for the pipeline to
recycle the request and task mid-session, and for the matcher to expose a
per-task reset — both of which Spike 5 had made requirements. It satisfies
the "audio processed on-device only" NFR with the same flag.

**Accuracy:** holds. 10.0% WER on-device against 8.2% server on the same
110-word passage, two words apart, with errors that barely overlap.
On-device costs effectively nothing.
Together with the result, **v1 should run on-device.**

**Revision locality:** fails. Revisions are not confined to the tail — 97
words back on-device, 135 on the server. _Stable-prefix counting as specified
does not hold, and the matcher cannot be built until it is redesigned around
a transcript that revises behind itself._

The most important thing this spike learned is the thing it was not looking
for. Going in, the working assumption was that deep revisions might be an
on-device artifact, and that the server path was the safe fallback. It is
not — the server is worse, and worse in a harder way. On-device fails
loudly and on a schedule: tail-local for 12-45 seconds, then one whole-segment
rewrite, then a roll. The server fails quietly and continuously: a single
early word oscillating for the entire life of the transcript, so no prefix is
ever safe at any depth at any time. _There is no configuration of
`SFSpeechRecognizer` in which the stable prefix is stable._ The matcher has
to be built for a transcript that revises behind itself, and the on-device
shape is the more tractable of the two to build against.

