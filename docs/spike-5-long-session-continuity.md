# Spike 5: Long Session Continuity

Script: [`spikes/spike5_long_session_continuity.py`](../spikes/spike5_long_session_continuity.py)

**Question:** Does a single `SFSpeechRecognizer` recognition task survive a
long session, or does it terminate after a fixed amount of audio? If it
terminates, does it do so loudly (an error) or silently, and does the audio
engine survive it?

Spikes 1-4 ran for only 5-20 seconds each, while the NFRs require the app to
run continuously in the background over long sessions. Nothing tested so far
spoke to that gap.

**Method:** Spikes [2](spike-2-stt-streaming.md)/[4](spike-4-filler-word-preservation.md)'s
script, with Spike 4's per-segment logging stripped: at ~10 lines per callback
it would bury the signal, and it prints on the main thread where the callback
fires ([Spike 3](spike-3-thread-safety.md)), competing with the run loop being
measured. Added 2 independent liveness counters -- `buffer_count` in
`tap_callback` for audio going in, `callback_count` in
`recognition_result_callback` for recognition coming out -- so a stall could be
attributed rather than guessed at. Added a silence detector warning when more
than 10s pass with no callback, and a 30s heartbeat printing buffers, callbacks
and `maxrss`. Extended the run window from 20s to 300s, speaking continuously
past the 60s, 90s and 120s marks.

**Result:**

The recognition task terminated on its own at **+61.54s**, flagged by
`isFinal=True`, and never fired again for the remaining 238.7s of the run
(79.5% of the session). No error was ever delivered — the `ERROR` branch
printed zero times.

Audio was unaffected throughout: `buffer_count` stood at ~613 when the task
died and climbed to 3000 by the end, at a steady ~10 buffers/sec, while
`callback_count` froze at 141.

The cutover, and the silence that followed:

```
[+  60.20s] -- heartbeat: buffers=600 callbacks=138 maxrss=33.5MB
[+  60.25s] #139  final=False chars=545   ...get that oh lol oh lol yeah I wonder for like
[+  61.41s] #140  final=False chars=545   ...get that oh lol oh lol yeah I wonder for like
[+  61.54s] #141  final=True  chars=545   ...get that oh lol oh lol yeah I wonder for like
[+  71.58s] !! NO CALLBACKS for 10.0s (buffers=714, callbacks=141)
[+  90.28s] -- heartbeat: buffers=901 callbacks=141 maxrss=34.8MB
[+ 120.30s] -- heartbeat: buffers=1201 callbacks=141 maxrss=34.8MB
[+ 150.31s] -- heartbeat: buffers=1501 callbacks=141 maxrss=34.8MB
[+ 180.32s] -- heartbeat: buffers=1801 callbacks=141 maxrss=34.8MB
[+ 210.37s] -- heartbeat: buffers=2102 callbacks=141 maxrss=34.8MB
[+ 240.43s] -- heartbeat: buffers=2402 callbacks=141 maxrss=34.9MB
[+ 270.46s] -- heartbeat: buffers=2703 callbacks=141 maxrss=34.9MB
Engine stopped.
SUMMARY: ran 300.2s | buffers=3000 | callbacks=141
         last callback at +61.54s
```

Buffer arrival was constant at ~10/sec regardless of whether speech was
happening — 300 buffers at +30s, 600 at +60s — putting the cap at roughly
600 buffers, i.e. about 60 seconds of recording.

**Interpretation:**

- **A hard ~60-second cap on a single recognition task is confirmed.** This
  is not a timeout from silence or a crash; the task completed normally at
  its limit while speech was still ongoing mid-sentence.
- **The audio pipeline is untouched by it.** The 2-counter design settles
  this: buffers kept flowing into a recognizer that had stopped consuming
  them. Without the split counters, "output stopped" would have been
  ambiguous between a dead mic, a dead engine, and a dead recognizer.
- **Termination is silent - there is no error to catch.** The `ERROR`
  branch never fired, and `isFinal=True` was the only signal. _Any restart
  logic must watch `isFinal`, not wait on an error._
- **The limit counts recording time, not talking time.** Buffers accrue
  whether or not the user is speaking.
- **Memory stayed flat, but this run barely tests it.** Peak memory rose 33.3MB
  → 34.9MB across 5 minutes with no runaway growth, but `ru_maxrss` is a
  high-water mark that can only climb, and recognition was dead for 238 of the
  300 seconds. The one representative window is the first 60s, where it moved
  33.3MB → 33.5MB. A real leak test needs current RSS sampled while recognition
  is actually running.
- **On the server path a session outlives a single recognition task**, which made
  task-restart a v1 requirement: recycle the request and task while keeping the
  engine and tap alive. _What outlived it is that the running counts must survive
  a transcript reset, which still happens every 12-45 seconds._

**Status:** Spike complete. A single `SFSpeechRecognizer` task terminates after
about 61.5 seconds of recording, silently, via `isFinal=True` with no error,
while the audio engine and tap keep running normally — closing the gap left by
Spikes 1-4 having run for only 5-20 seconds. Memory was stable across 5 minutes,
though only weakly tested. _The restart work this implied was retired by
[Spike 6](spike-6-on-device-recognition.md), which found no such cap on the
on-device path._
