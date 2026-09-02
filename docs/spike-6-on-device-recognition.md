# Spike 6: On-Device Recognition & Revision Locality

Script: [`spikes/spike6_on_device_recognition.py`](../spikes/spike6_on_device_recognition.py)

**Question:** Two questions [Spike 5](spike-5-long-session-continuity.md) left open. Does the ~60s recognition-task
cap survive `requiresOnDeviceRecognition = True`? And are partial-result
revisions confined to the tail of the transcript, as stable-prefix counting
assumes? Spike 5 could not answer the second: its log truncated to the last 45
characters, so the front of the transcript was never observed.

**Method:** Spike 5's script copied to `spike6_on_device_recognition.py` and
extended in 3 ways, keeping the 2-counter design (buffers in, callbacks
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

A `--selftest` flag checks `find_revision` against 7 synthetic cases
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
callbacks for the entire 5 minutes, `isFinal` never fired once, and memory
stayed flat at 32.8MB → 33.2MB with recognition actually working the whole
time.

But the transcript is not one growing string. It resets to empty roughly
every 12-45 seconds, 13 times across the run, with no `isFinal` and no
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
within-segment rewrites and 13 are resets — the 10 above plus 3 that
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

The 9 deep ones are the finding:

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

Every one of the 9 is followed by a segment reset within 0.8 seconds, and
8 of the 9 within 0.2. The correlation is 9 out of 9 in that
direction, but not in reverse: 13 resets against 9 deep revisions
means 4 segments rolled over with no close-out pass at all. A
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
where the server did not. **All 3 instances of "like" survived intact in
both.**

And the revision depths, which is where the 2 paths differ most:

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
`as` ↔ `is` (and `ridden` ↔ `written`) at least 9 times across the run,
and each flip re-emits everything downstream as changed.

**Interpretation:**

- **`requiresOnDeviceRecognition` removes the ~60s cap.** A single task ran the
  full 5 minutes with `isFinal` never firing, where the server-based Spike 5 task
  died silently at +61.54s. The same flag satisfies the "audio processed
  on-device only" requirement.
- **The cap was replaced rather than removed.** The task survives, but the
  transcript still rolls over every 12-45 seconds, and where Spike 5 at least
  announced its death with `isFinal=True`, this has no signal at all. The only
  way to know a segment ended is to notice the transcript no longer extends what
  came before.
- **Revisions are not confined to the tail, on either path.** On-device reached
  97 words back and the server 135, with 22 of the server's 40 revisions going
  10+ words back against 19 of on-device's 77. Stable-prefix counting is broken
  by `SFSpeechRecognizer` generally, so falling back to the server is no escape.
- **The deep revisions have a shape, and the 2 paths differ in it.** Every deep
  revision on-device is a close-out: a full re-decode of a segment immediately
  before discarding it. Within a segment, 64 of 64 revisions stay within 6 words
  of the tail and 45 within 2 — so on-device is quiet then loud, tail-local for
  12-45 seconds then one whole-segment rewrite. The server is continuously
  unstable instead, an early word oscillating for the life of the transcript, so
  no prefix is ever safe.
- **A close-out cannot be read as the signal that a roll is coming.** 4 of the 13
  rolls had no deep revision in front of them.
- **The close-out materially changes words.** "county words" → "counting words",
  "we're nothing" → "where nothing", "wanna know" → "one note". A count taken
  before the close-out and one taken after are counts of different text.

> [!NOTE]
> **_Side findings_**
>
> `find_revision` measures from the first changed character to the end of the old
> text, so its word counts overstate how many words actually changed — the server
> flipping `as` ↔ `is` at character 93 of 787 reports 135 words back. The depth
> is what stable-prefix counting cares about and is accurate; the magnitude is
> not.

**Status:** Spike complete, all 3 questions answered: the cap is gone on-device
, and revision
locality fails on both paths. The surprise was that the server is the worse of
the 2, rather than the safe fallback it was assumed to be — a matcher can wait
for a close-out, but not for an oscillation that never settles. The matcher was
therefore built for a transcript that revises behind itself.
