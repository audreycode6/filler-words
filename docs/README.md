# Documentation

Two kinds of writing live here. A spike file is the record of one exploratory
run: the question it set out to answer, how it was built, what it measured, and
what was still open when it ended. [`design-decisions.md`](design-decisions.md)
is where a question stops being open — each decision there draws on more than
one run, which is why it sits apart from any single spike.

## Spikes

| Spike | Question | Finding |
| --- | --- | --- |
| [1 — Mic Permission + Raw Audio Capture](spike-1-mic-permission.md) | Can the app prompt for microphone access and read raw audio? | Capture works through AVAudioEngine. A denied permission raises no error and returns silent zeros, so authorization status has to be read directly. |
| [2 — Speech To Text Streaming](spike-2-stt-streaming.md) | Does the recognizer stream text as you speak, or hand back whole utterances after a pause? | It streams. Text arrives incrementally, and already-delivered words can be silently corrected or withdrawn. |
| [3 — Thread Safety](spike-3-thread-safety.md) | Which thread does the recognition callback arrive on? | The main thread, in this environment. Any real AppKit interface still needs an `NSApplication` bootstrap. |
| [4 — Filler Word Preservation](spike-4-filler-word-preservation.md) | Does the recognizer preserve sound-based disfluencies anywhere in its output? | No. "um" and "uh" are absent from `formattedString()` and from `segments()` alike, so they cannot be counted at any level. |
| [5 — Long Session Continuity](spike-5-long-session-continuity.md) | Can one recognition task run for the length of a real session? | No. The task stopped at about 61 seconds with no error raised, the third silent failure found in this stack. |
| [6 — On-Device Recognition & Revision Locality](spike-6-on-device-recognition.md) | Does on-device recognition lift that cap, and do revisions stay at the tail of the transcript? | The cap is gone — 300 seconds ran uninterrupted, at 10.0% word error against 8.2% for the server. Revisions reach anywhere in the transcript, which retired stable-prefix counting. |

## Design decisions

[`design-decisions.md`](design-decisions.md) holds five:

- **Choosing what the app counts** — the app counts a list of tracked words,
  meaning the vocabulary someone has decided to drop from their speech, and how
  that list is written, scoped, and changed.
- **Counting tracked words in a revising transcript** — how a count is taken
  from a transcript the recognizer keeps rewriting underneath it.
- **Holding the totals of one session** — what one stretch of listening keeps,
  which numbers are derived from it, and why the measure of a habit is tracked
  words per minute.
- **Streaming speech from the microphone** — what the app checks before it
  starts listening and what it refuses to run without.
- **Showing one session in the menu bar** — where the interface reads its
  numbers from, and what order the words are listed in.

## Writing a spike file

So that a seventh spike reads like the first six, each write-up carries the
same sections: **Question**, **Method**, **Result**, **Interpretation**,
**Deferred Decisions**, **Question Moving Forward**, and **Status**. Aim for
two or three sentences on the question asked, what was found, and what it means
for the design. Write the method as prose when the spike used a single
technique, and as a numbered list when it had several build steps in sequence.

Each file opens with a link to the script under [`../spikes`](../spikes) that
produced its measurements. The scripts stay runnable, so a finding can be
checked rather than taken on faith.
