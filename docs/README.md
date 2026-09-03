# Documentation

Three kinds of writing live here. A spike file is the record of one exploratory
run: the question it set out to answer, how it was built, what it measured, and
what it meant for the design. [`design-decisions.md`](design-decisions.md) is
where a question stops being open — each decision draws on more than one run,
which is why it sits apart from any single spike. What the runs left unanswered
is gathered under What's still open.

## Spikes

| Spike | Finding |
| --- | --- |
| [1 — Mic Permission + Raw Audio Capture](spike-1-mic-permission.md) | Capture works through AVAudioEngine. A denied permission raises no error and returns silent zeros, so authorization status has to be read directly. |
| [2 — Speech To Text Streaming](spike-2-stt-streaming.md) | Recognition streams. Text arrives incrementally, and already-delivered words can be silently corrected or withdrawn. |
| [3 — Thread Safety](spike-3-thread-safety.md) | The callback fires on the main thread, in this environment. Any real AppKit interface still needs an `NSApplication` bootstrap. |
| [4 — Filler Word Preservation](spike-4-filler-word-preservation.md) | "um" and "uh" are absent from `formattedString()`, `segments()` and `alternativeSubstrings()` alike, so they cannot be counted at any level. |
| [5 — Long Session Continuity](spike-5-long-session-continuity.md) | A recognition task stops at about 61 seconds with no error raised, while the audio engine keeps running. |
| [6 — On-Device Recognition & Revision Locality](spike-6-on-device-recognition.md) | On-device lifts that cap — 300 seconds ran uninterrupted, at 10.0% word error against 8.2% for the server. Revisions reach anywhere in the transcript, which retired stable-prefix counting. |

## Design decisions

[`design-decisions.md`](design-decisions.md) holds 5, one per part of the app:
choosing what the app counts, counting tracked words in a revising transcript,
holding the totals of one session, streaming speech from the microphone, and
showing one session in the menu bar.

## What's still open

Questions a run raised and left unsettled, from a spike or from the app itself.
Each names where it came from.

- **Packaging the app as its own signed application.** Spikes 1, 2, 3 and 5 each
  left something to re-check once the app stops running from a source checkout:
  whether the permission prompt appears under the app's own identity, whether
  the run loop still has to be pumped by hand, whether the recognition callback
  still arrives on the main thread, and whether the recognition cap behaves the
  same.
- **Acoustic detection of sound-based disfluencies.** Spike 4 established that
  "um" and "uh" cannot be recovered from the recognizer's text at any level.
  Reading them from the raw audio buffer instead, alongside recognition rather
  than through it, is a possible later expansion.
- **What decides when a segment ends.** Spike 6 measured segments running 12 to
  45 seconds with no evident cause. A tracked word is counted only once its
  segment rolls over, so until the range has a known limit, the longest that
  wait can be is unknown.
- **Whether a close-out pass can rewrite text from 2 segments back.** Counting
  by segment assumes it cannot, since that text has already been counted and a
  change to it could only be corrected by counting down. Spike 6 saw nothing
  suggesting it happens and did not test it directly.
- **What decides when a recognition task ends.** One ended after 44 seconds of
  quiet, reporting `kLSRErrorDomain` code 300, while a later run outlived 116
  seconds of it, so silence alone does not account for it. The rate that reports
  a failing recognizer, 3 replacements inside 30 seconds, rests on those 2
  observations.
- **Identifying a recognizer that returns nothing from a room with no speech in
  it.** In both, audio keeps arriving and transcripts stop, so nothing in the
  app separates them and a session counting nothing looks healthy. Reading the
  loudness of each buffer would separate them -- needs a threshold measured
  against one microphone and one room.

## Writing a spike file

So that a seventh spike reads like the first six, each write-up carries the same
sections: **Question**, **Method**, **Result**, **Interpretation**, and
**Status**. Method names the spike it built on and what it changed, rather than
restating the script. Anything a run leaves open belongs under What's still open
above. Aim for 2 or 3 sentences on the question asked, what was found, and what
it means for the design.

Each file opens with a link to the script under [`../spikes`](../spikes) that
produced its measurements. The scripts stay runnable, so a finding can be
checked rather than taken on faith.
