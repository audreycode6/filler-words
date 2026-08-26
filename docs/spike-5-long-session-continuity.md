# Spike 5: Long Session Continuity

Script: [`spikes/spike5_long_session_continuity.py`](../spikes/spike5_long_session_continuity.py)


**Question:** Does a single `SFSpeechRecognizer` recognition task survive a
long session, or does it terminate after a fixed amount of audio? If it
terminates, does it do so loudly (an error) or silently, and does the audio
engine survive it?

Spikes 1-4 ran for only 5-20 seconds each, while the NFRs require the app to
run continuously in the background over long sessions. Nothing tested so far
spoke to that gap.

**Method:**

1. Copy Spike [2](spike-2-stt-streaming.md)/[4](spike-4-filler-word-preservation.md)'s script as the base (permission checks, request +
   recognizer + tap setup, run-loop pump).
2. Strip Spike 4's per-segment logging (`segments()` +
   `alternativeSubstrings()`). That question is answered, and at ~10 lines per
   callback it would bury the signal — and it prints on the main thread, where
   the callback fires ([Spike 3](spike-3-thread-safety.md)), competing with the run loop being measured.
3. Replace the transcript print with one compact line per callback: elapsed
   time, callback number, `isFinal`, transcript length in characters, and the
   last 45 characters of text.
4. Add two independent liveness counters: `buffer_count`, incremented in
   `tap_callback` (audio going _in_), and `callback_count`, incremented in
   `recognition_result_callback` (recognition coming _out_).
5. Unpack the error branch into `error.domain()`, `error.code()`, and
   `error.localizedDescription()` rather than printing the raw `NSError`.
6. Add a silence detector to the run loop: warn once per episode when more
   than 10s pass with no callback.
7. Add a 30s heartbeat printing buffers, callbacks, and `maxrss`.
8. Extend the run window from 20s to 300s, and speak continuously,
   deliberately pushing past the 60s / 90s / 120s marks.
9. Print an end-of-run summary with the timestamp of the last callback.

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
- **The audio pipeline is untouched by it.** The two-counter design settles
  this: buffers kept flowing into a recognizer that had stopped consuming
  them. Without the split counters, "output stopped" would have been
  ambiguous between a dead mic, a dead engine, and a dead recognizer.
- **Termination is silent - there is no error to catch.** The `ERROR`
  branch never fired, and `isFinal=True` was the only signal. _Any restart
  logic must watch `isFinal`, not wait on an error._ This is the third
  silent-failure mode in this stack, after [Spike 1](spike-1-mic-permission.md)'s silent permission
  denial and Spike 2's silently dropped streaming results.
- **The limit counts recording time, not talking time.** Buffers accrue
  whether or not the user is speaking, so a quiet user burns the 60 seconds
  just as fast as a talkative one. Staying quiet doesn't buy more time.
- **Memory stayed flat, but this run tests it only weakly.** Peak memory
  went from 33.3MB at +30s to 34.9MB at the end — a 1.6MB rise across five
  minutes, with no sign of runaway growth. Two things limit what that
  proves. First, `ru_maxrss` reports the _highest_ memory the process has
  ever used, not what it is using now, so the number can only climb and
  can never show memory being released. Second, recognition was dead for
  238 of the 300 seconds, so most of the run measured a mostly-idle
  process rather than a working one. The only representative window is the
  first 60s, where memory moved 33.3MB → 33.5MB. _A proper leak test needs
  current RSS sampled across a long session with recognition actually
  running, which isn't possible until task-restart exists._
- **This makes task-restart a v1 requirement.** A session
  longer than a minute is the normal case, not an edge case, so the pipeline
  must recycle the request and task transparently while keeping the engine
  and tap running.
- **A session now contains many recognition tasks, and the matcher's state
  has to reflect that.** Before this spike, a session and a recognition task
  looked like the same thing. They aren't: the prefix-tracking state used to
  diff one transcript against the next is only meaningful within a single
  task, while the running counts have to survive across all of them. A
  restart must clear the first without disturbing the second, and must count
  the unsettled tail of the dying task before discarding it — otherwise the
  end of a sentence is lost roughly once a minute, all session long.

> [!NOTE]
> **_Side findings (not this spike's question)_**
>
> - Four more "like" instances (`#94`, `#98`, `#113`, `#139`) and a "so"
>   (`#90`) transcribed correctly, adding to Spike 4's evidence that
>   real-word fillers survive reliably.
> - **Roughly half of those "like" instances were not fillers** — "it seems
>   like" (`#113`) and "someone will like" (`#98`) are ordinary usage, while
>   `#94` and `#139` are filler use. This came from a minute of unscripted
>   speech with no attempt to produce false positives, which suggests the
>   filler-vs-verb "like" ambiguity the TDD flags is the common case, not an
>   edge case. A naive `\blike\b` matcher would have roughly doubled the true
>   count on this sample.
> - No profanity filtering was applied in this configuration, unlike the
>   disfluency filtering found in Spike 4.

**Deferred Decisions:**

- Whether to set `requiresOnDeviceRecognition = True` is untested here. If
  on-device recognition has no equivalent cap, that single flag would remove
  the restart problem entirely _and_ satisfy the "audio processed on-device
  only" NFR — worth testing before building a restart mechanism that may not
  be needed. Possible tradeoff in accuracy, unmeasured.
- The shape of the restart mechanism (recycle request + task while keeping
  the engine and tap alive vs. tearing down the whole pipeline) is
  implementation work for the app's audio layer, deliberately not built
  here.
- The shape of the matcher's reset — one method, two with different scopes, or state
  the pipeline owns rather than the matcher — is matcher implementation
  work, deliberately not designed here. _Settled — see **Design decisions**
  at the end of this file: the previous transcript is held by a separate
  tracker, so the matcher has no reset to shape._

**Question Moving Forward:**

- Does `requiresOnDeviceRecognition` remove the ~60s cap? Test before
  building restart logic.
- How long is the restart gap in practice, and how much speech is lost per
  cycle? Every ~60 seconds of a session pays this cost.
- Re-verify the cap and the restart behavior once the app is packaged with
  its own run loop.
- Are partial-result revisions always confined to the tail of the
  transcript? Stable-prefix counting depends on this, and this run could not
  test it — the log truncates to the last 45 characters, so the front of the
  transcript was never observed. Verify with a run that logs full
  transcripts before relying on the assumption in the matcher.

**Status:** Spike complete, core question answered: a single
`SFSpeechRecognizer` task terminates after about 61.5 seconds of recording,
silently, via `isFinal=True` with no error, while the audio engine and tap
continue running normally. Memory was stable across five minutes, though
only weakly tested. This closes the gap left by Spikes 1-4 having run for
only 5-20 seconds. Before this spike it was unknown whether the app would
need to restart recognition mid-session. It does — about once a minute,
for as long as a session runs. That work now belongs in v1: the audio
pipeline has to restart the task without the user noticing, and the
matcher has to cope with the transcript resetting to empty each time.
Carried forward: whether on-device recognition has the same cap.
If it doesn't, none of that restart work is needed.

