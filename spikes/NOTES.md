# Findings/answers from each spike

<!-- Write 2-3 sentences: question asked, findings, what it means for the design.
    Method: use prose for a single technique, a numbered list when
    the spike has multiple sequential build steps. -->

## Spike 1 Mic Permission + Raw Audio Capture:

**Question:** Can I get a permission prompt to appear, grant it, and print raw
audio sample data to the console for 5 seconds?

**Method:** AVAudioEngine + installTap via PyObjC, printing frame count and
peak amplitude per chunk for 5 seconds.

**Result:**
No permission dialog ever appeared. First run produced an all-zero
signal (0.0000 peak amplitude every chunk) with no error or exception; engine
ran and "succeeded" but returned silence. Checked System Settings > Privacy &
Security > Microphone and found the host process (VS Code) had mic
access toggled off. After manually enabling it, the script ran without any
prompt and returned real audio data (background noise ~0.002-0.003, rising to
0.1-1.0+ while speaking).

Added an explicit authorization status check (`AVCaptureDevice.
authorizationStatusForMediaType_`) at the top of the script, printed before
engine init. Verified it correctly reports `authorized (3)` and `denied (2)`
by toggling the System Settings permission and re-running; confirms the
app can know its permission state up front rather than inferring it from
silent audio output.

Transcript output examples:

- the `max (peak amplitude)` field demonstrates how input dialogue produces a range of different audio amplitude

```
# Successfuly getting audio
Mic permission status: authorized -- good to go!
Engine started - talk now...
frames (chunk size) = 4800 | max (peak amplitude) = 0.1352
frames (chunk size) = 4800 | max (peak amplitude) = 0.1561
frames (chunk size) = 4800 | max (peak amplitude) = 0.1439
frames (chunk size) = 4800 | max (peak amplitude) = 0.1262
frames (chunk size) = 4800 | max (peak amplitude) = 0.1295
...
frames (chunk size) = 4800 | max (peak amplitude) = 0.0218
frames (chunk size) = 4800 | max (peak amplitude) = 0.3636
frames (chunk size) = 4800 | max (peak amplitude) = 0.7670
frames (chunk size) = 4800 | max (peak amplitude) = 0.7054
frames (chunk size) = 4800 | max (peak amplitude) = 0.4409
frames (chunk size) = 4800 | max (peak amplitude) = 0.3591
frames (chunk size) = 4800 | max (peak amplitude) = 0.3025
frames (chunk size) = 4800 | max (peak amplitude) = 0.2837
frames (chunk size) = 4800 | max (peak amplitude) = 0.2644
frames (chunk size) = 4800 | max (peak amplitude) = 0.2513
frames (chunk size) = 4800 | max (peak amplitude) = 0.1796
frames (chunk size) = 4800 | max (peak amplitude) = 0.0303
frames (chunk size) = 4800 | max (peak amplitude) = 0.0048
frames (chunk size) = 4800 | max (peak amplitude) = 0.9966
frames (chunk size) = 4800 | max (peak amplitude) = 0.9744
frames (chunk size) = 4800 | max (peak amplitude) = 0.9990
frames (chunk size) = 4800 | max (peak amplitude) = 0.8440
frames (chunk size) = 4800 | max (peak amplitude) = 0.5894
frames (chunk size) = 4800 | max (peak amplitude) = 0.1606
frames (chunk size) = 4800 | max (peak amplitude) = 0.0091
frames (chunk size) = 4800 | max (peak amplitude) = 0.9927
frames (chunk size) = 4800 | max (peak amplitude) = 1.0113
Engine stopped.
```

```
# Permission denied — engine reports success, audio is empty:
Mic permission status: denied
Engine started - talk now...
frames (chunk size) = 4800 | max (peak amplitude) = 0.0000
frames (chunk size) = 4800 | max (peak amplitude) = 0.0000
frames (chunk size) = 4800 | max (peak amplitude) = 0.0000
...
Engine stopped.
```

**Interpretation:**

- **Permission denial is silent, not an exception.** Code that assumes "no error
  = mic is working" would be wrong. _Any real app should explicitly check/request
  authorization status rather than assuming._
- **The permission prompt/toggle is tied to the _host process_ (e.g. VS Code/Terminal),
  not to this script individually.** This is expected for a bare interpreted
  script. --_see Deferred Decisions below for more details_

> [!NOTE]
>
> - Noticed **some peak amplitude values slightly above 1.0 (clipping) when
>   speaking close/loud to the mic.** No impact on filler-word detection (doesn't
>   use amplitude), noting only in case a future feature (e.g. input level meter)
>   cares about it.
> - **Kept the `startAndReturnError_` error-handling branch even though it never
>   fired in testing**; a denied/not-determined status doesn't cause the engine
>   to fail, it just returns silent zeros, so this branch is guarding a
>   different failure class entirely (missing input device, session conflicts,
>   format mismatches). Untested but cheap to keep.

**Deferred Decisions:**

- How the UI should react to a denied/not-determined status (e.g. showing a
  message directing the user to System Settings) is UX/state-machine work
  for the app's UI layer; deliberately not built here to keep the spike scoped
  to "can I detect + read permission state," not "how should the app respond
  to it."
  - _A packaged .app with its own Info.plist + `NSMicrophoneUsageDescription`
    should get its own first-launch prompt tied to its own identity, but this is
    unverified until the app is actually bundled._

**Question Moving Forward:** Confirm mic permission prompt behavior once the app is
packaged as a real .app bundle with Info.plist. Don't assume it'll "just work"
the same way.

**Status:** Core question answered: raw audio capture via AVAudioEngine/PyObjC
works, and permission state is now explicitly observable rather than inferred.

## Spike 2 Speech To Text Streaming:

**Question:**
Regarding, STT engine logistics, does it support continuous streaming (text arrives incrementally as you speak) or only discrete utterances (you get a full result only after a pause). How does threading look like?:

- If streaming: your Filler-word matcher can run on partial text as it arrives — genuinely near-real-time.
- If discrete/utterance-based: detection happens in bursts after each pause. Means you should expect speech to be "detected within N seconds of the pause" rather than continuous mid-sentence detection.

**Method:**

1. Status Checks: Mic Permissions Status Check & Speech Recognition Permissions Status Check
2. Create a `SFSpeechAudioBufferRecognitionRequest` instance & call `.setShouldReportPartialResults_(True)` which gives incremental partial results as speech comes in (_blocked initially by a TCC crash requiring `NSSpeechRecognitionUsageDescription` --see Environment Issue below_)

3. Create an `SFSpeechRecognizer` instance
4. Start a recognition task with request
5. Initialize engine and install tap (from spike 1) which will take in `tap_callback`.
6. Start engine and speak sentence with midsentence pause to determine if streaming or discrete speech results.

> [!NOTE]
> **_Environment Issue Notes: Speech permission crash tied to "responsible process"_**
>
> - While setting up speech authorization, `requestAuthorization_()` crashed with
>   a TCC error demanding `NSSpeechRecognitionUsageDescription` in Info.plist.
>   Adding that key to the system Python.app's Info.plist had no effect.
> - **Root cause:** macOS TCC attributes permission requests to the "responsible
>   process", i.e. the app that launched the script, not the script/interpreter
>   itself. Running via VS Code's integrated terminal made _VS Code_ the
>   responsible process, and VS Code's Info.plist is missing
>   `NSSpeechRecognitionUsageDescription` (a known gap, confirmed via an open
>   VS Code GitHub issue). This is also why mic access worked untouched from
>   day one — VS Code's Info.plist already includes that key.
> - **Fix:** Run the script from macOS's built-in Terminal.app instead of VS
>   Code's integrated terminal. Terminal.app is a valid responsible process with
>   the necessary keys already present; permission dialog appeared and was
>   granted normally.
> - _This is a dev-environment quirk only. Once the real app is packaged as its own signed `.app`, it becomes its own
>   responsible process and this issue doesn't apply._

**Result:**
Text showed up and stabilized before the pause finished, well ahead of resuming speech, i.e. a clean "streaming, not discrete" result.

Actual transcript timestamps:

```
Engine started - talk now...
[+2.18s] I like
[+2.27s] I like to
[+2.47s] I like to eat
[+3.18s] I like to eat watermelon
[+3.28s] I like to eat watermelon's
[+3.40s] I like to eat watermelon's
[+3.49s] I like to eat watermelon's
[+6.07s] I like to eat watermelon's I also
[+6.21s] I like to eat watermelon's I also like
[+6.38s] I like to eat watermelon's I also like to
[+6.58s] I like to eat watermelon's I also like to drink
[+6.87s] I like to eat watermelon's I also like to drink water
[+7.19s] I like to eat watermelon's I also like to drink watermelon
[+7.47s] I like to eat watermelon's I also like to drink watermelon flavored
[+7.97s] I like to eat watermelon's I also like to drink watermelon flavored soda
[+8.08s] I like to eat watermelon's I also like to drink watermelon flavored soda
[+8.79s] I like to eat watermelon's I also like to drink watermelon flavored soda one
[+9.20s] I like to eat watermelon's I also like to drink watermelon flavored soda one to
[+9.58s] I like to eat watermelon's I also like to drink watermelon flavored soda one two
[+9.74s] I like to eat watermelon's I also like to drink watermelon flavored soda 12
[+9.94s] I like to eat watermelon's I also like to drink watermelon flavored soda 123
Engine stopped.
```

- Partial text "[+3.28s] I like to eat watermelon's" stabilized by +3.28s
- ~2.5s silence gap (deliberate pause):
  - "[+3.49s] I like to eat watermelon's"
  - "[+6.07s] I like to eat watermelon's I also"
- Words stream in well before you'd call the pause "finished".
  - deliberate pause happened after [+3.49s] and already had text: "I like to eat watermelon's".

**Interpretation:**

- **Streaming confirmed**: filler-word matcher can run on partial text near-real-time
- **Partial results are provisional, not append-only** — transcript shows this: "watermelon" on 1 timestamp transcription → "watermelon's" in a following timestamp transcription. Another example: "one" → "one two" → "12" → "123". The recognizer revises earlier words as more context arrives.
  - _This is a real design constraint: a filler-word detector can't just naively append/flag words as they first appear; it needs to handle a word it flagged getting silently corrected/retracted a moment later._

**Deferred Decision:** Open Question: How should the filler-word matcher handle retracted/revised partial text?

**Question Moving Forward:** Confirm if run-loop-pump is necessary once packaged app.

- During `success, error = audio_engine.startAndReturnError_(None)` `time.sleep()` alone silently drops streaming results in a bare script; needed to actively pump NSRunLoop. It's unverified whether a real packaged app (with its own Cocoa/AppKit event loop already running) needs this workaround at all.

**Status:**
Spike complete, core question answered (streaming confirmed), plus the two carried-forward caveats (run-loop behavior in a packaged app, revision/retraction handling) as open items for later.

## Spike 3 Thread Safety

**Question:** What thread do STT partial-result callbacks actually fire on, and is it safe to mutate UI-facing state directly from there, or does it need explicit main-thread dispatch?

**Method:**

1. Copy Spike 2's script as the base (permission checks, request +
   recognizer + tap setup, run-loop pump).
2. Inside the `recognition_result_callback`, add a log about whether you're on the main thread — via `NSThread.isMainThread()`. Run it, talk, and just read the log. This answers "is this even a background thread in practice".
3. Create the UI stand-in using `AppKit`, before the tap install.
4. Test the risk. Mutate UI stand-in unsafely from callback (`recognition_result_callback`). Watch three places: the terminal (crash trace or console warning), the actual menu bar (does the title update live, lag, or not at all), and the "On main thread: ..." log from Step 2 (should confirm False if this is indeed a background callback).
5. Wrap the same call in `dispatch_async` (PyObjC exposes it from libdispatch) and re-run, to compare behavior against Step 4.

> [!NOTE]
> **_Environment Issue: `NSStatusItem` creation crashed with `CGSConnectionByID` assertion_**
>
> - Creating a real AppKit UI object (`NSStatusItem`) crashed immediately with
>   `CGAtomicGet(&is_initialized)` failing inside `CGSConnectionByID`; before
>   ever reaching the callback under test.
> - **Root cause:** any real AppKit UI object requires an active `NSApplication`
>   instance to have opened a WindowServer connection first. A bare script that
>   only imports `AppKit` without instantiating `NSApplication` has no such
>   connection.
> - **Fix:** Create an instance of `NSApplication` before creating the
>   status item: `app = AppKit.NSApplication.sharedApplication()`
>   - For a menu-bar-only app, `app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)` is also typically needed.

**Result:**

Transcript timestamps (Step 2):

```
Engine started - talk now...
On main thread: True
[+2.17s] Hi
On main thread: True
[+2.61s] Hi I think I
On main thread: True
[+2.99s] Hi I think I just
On main thread: True
[+3.61s] Hi I think I just realize the
On main thread: True
[+3.83s] Hi I think I just realized the
On main thread: True
[+3.93s] Hi I think I just realize the
On main thread: True
[+3.98s] Hi I think I just realize the bug
On main thread: True
[+4.29s] Hi I think I just realize the bug I'm
On main thread: True
[+4.40s] Hi I think I just realize the bug I'm going
On main thread: True
[+4.50s] Hi I think I just realize the bug I'm going to
On main thread: True
[+4.59s] Hi I think I just realize the bug I'm gonna to
On main thread: True
[+4.79s] Hi I think I just realize the bug I'm gonna be
On main thread: True
[+5.07s] Hi I think I just realize the bug I'm gonna be be
On main thread: True
[+5.17s] Hi I think I just realize the bug I'm gonna be be saying
On main thread: True
[+5.36s] Hi I think I just realize the bug I'm going to be saying
On main thread: True
[+5.46s] Hi I think I just realize the bug I'm going to be saying
On main thread: True
[+8.27s] Hi I think I just realize the bug I'm going to be saying oh no
On main thread: True
[+8.78s] Hi I think I just realize the bug I'm going to be saying oh no I don't
On main thread: True
[+8.88s] Hi I think I just realize the bug I'm going to be saying oh no I don't know
On main thread: True
[+9.07s] Hi I think I just realize the bug I'm going to be saying oh no I don't know if
On main thread: True
[+9.21s] Hi I think I just realize the bug I'm going to be saying oh no I don't know if this
On main thread: True
[+9.40s] Hi I think I just realize the bug I'm going to be saying oh no I don't know if this is
On main thread: True
[+9.88s] Hi I think I just realize the bug I'm going to be saying oh no I don't know if this is actually
Engine stopped.
```

- Step 2: `On main thread: True` on every single callback firing, no exceptions.
- Step 4: visually confirmed the status-bar title updated live, in sync with
  each partial transcript, no lag or missed updates — direct, unwrapped
  mutation from the callback.

> [!NOTE]
> **_Side finding (not this spike's question) — filler words missing from transcript_**
>
> "um" never appeared in the transcript despite being spoken multiple times;
> "oh" is tracked only because it landed inside a real phrase ("oh no").
> `SFSpeechRecognizer`'s `formattedString()` is dictation-style output and
> likely strips disfluencies by design before they ever reach your code.
> **Motivates Spike 4:** does `SFTranscription.segments()` preserve filler
> words even when `formattedString()` doesn't?

**Interpretation:**

- **Callback confirmed to fire on the main thread** — contrary to the common
  assumption that STT callbacks run on a background thread by default.
- **Step 4 could not reproduce a genuine cross-thread violation**, because
  the callback never leaves the main thread in this environment. Direct UI
  mutation "worked" (i.e. status bar updated live with no crash, lag, or warning) but that's a consequence of never actually crossing threads, not proof
  that direct mutation is safe from a background thread in general.
- **Step 4 and Step 5 produced identical behavior**, confirming the
  `dispatch_async` wrap adds no observable cost or side effect when layered
  on top of a callback that's already on the main thread. This spike did
  not reproduce an actual cross-thread violation, so it doesn't demonstrate
  that the wrap _fixes_ anything — only that adopting it as a standing habit
  is free. Whether it actually prevents a crash under a genuine background-
  thread mutation remains untested here.

**Deferred Decision:** How the real app structures calling `dispatch_async` everywhere UI state
is touched (a shared helper/decorator vs. wrapping each call site
individually) is implementation-shape work, deliberately not built here.

**Question Moving Forward:** Confirm whether `SFSpeechRecognizer`'s callback
still fires on the main thread once the app is packaged (with its own
`NSApplication`/run loop already running) and under different recognition
configurations (e.g. `requiresOnDeviceRecognition`). Keep the `dispatch_async`
wrap regardless as defensive practice - don't rely on this spike's
main-thread finding holding universally.

**Status:**
Spike complete, core question answered: the callback fires on the main thread in this environment, so direct UI mutation worked cleanly and the dispatch_async wrap added no cost. No genuine cross-thread violation was ever produced in this spike, so its protective value rests on `dispatch_async`'s well-established general behavior, not on anything demonstrated here. Carried forward: the `NSApplication` bootstrap requirement for any real AppKit UI object.

## Spike 4 Filler Word Preservation

**Question:** Does `SFSpeechRecognizer` preserve filler words ("um", "uh",
"like") anywhere in its output, even if stripped from `formattedString()`?

**Method:**

1. Copy Spike 2's script as the base (permission checks, request +
   recognizer + tap setup, run-loop pump).
2. In `recognition_result_callback`, iterate
   `result.bestTranscription().segments()` and print each segment's
   `.substring()` and `.confidence()`, alongside the existing
   `formattedString()` print.
3. Also print each segment's `.alternativeSubstrings()` if non-empty.
4. Speak a test sentence with several clearly-enunciated "um"/"uh"/"like"
   fillers placed cleanly between real words.
5. Run a control sentence with no filler words, to sanity-check the
   segment-printing code itself.
6. Compare: do filler words ever appear in `segments()` or
   `alternativeSubstrings()`, even when absent from `formattedString()`?

**Result:**

Across two runs (9 usable filler-word instances: 4 "um", 5 "uh"), 0 fillers were recoverable at any level
tested: not in `formattedString()`, not as a segment `.substring()`, and
not in any segment's `.alternativeSubstrings()`. Empty on every segment,
every run — including on real words, suggesting this recognizer
configuration doesn't populate alternatives at all.

- Run 1 (not shown in the table below, but counted in the tally): the spoken
  sentence "My name UM is not UM bob sherbert" produced the transcript "My
  name is not Bob sherbet" — both "um" instances dropped with zero trace.
- Run 2 spoken sentence: "My name UM is not UH bob sherbert. UH I like love
  that UH short UH hairdo. And I think UH I'm going to UM talk about." Final
  settled transcript: "My name is not a Bob sherbet I like love that a short
  hairdo and I think I'm going to him talk about."

Run 2 word-by-word alignment (spoken vs. transcribed):

- "My name" → My name (normal)
- **UM** → _(nothing)_ — dropped
- "is not" → is not (normal)
- **UH** → **'a'** — substituted
- "bob sherbert" → Bob sherbet (normal)
- **UH** → _(nothing)_ — dropped
- "i like love that" → I like love that (normal)
- **UH** → **'a'** — substituted
- "short" → short (normal)
- **UH** → _(nothing)_ — dropped
- "hairdo" → hairdo (normal)
- "and i think" → and I think (normal)
- **UH** → _(nothing)_ — dropped
- "im going to" → I'm going to (normal)
- **UM** → **'him'** — substituted
- "talk about" → talk about (normal)

Combined tally: 6 of 9 fillers silently dropped with no trace; 3 of 9
replaced with a real, phonetically-similar, contextually-plausible word
("uh" → "a" ×2, "um" → "him" ×1); 0 of 9 recoverable via any tested API
surface.

Transcription excerpt (two consecutive firings, real logged output,
showing "a" appear at full confidence exactly where "uh" was spoken, then
collapse on the very next revision while the surrounding real words barely
move):

```
[+4.39s] My name is not a
  segment: 'My' (confidence=1.00)
  segment: 'name' (confidence=1.00)
  segment: 'is' (confidence=1.00)
  segment: 'not' (confidence=1.00)
  segment: 'a' (confidence=1.00)
[+4.49s] My name is not a
  segment: 'My' (confidence=0.93)
  segment: 'name' (confidence=0.92)
  segment: 'is' (confidence=0.92)
  segment: 'not' (confidence=0.92)
  segment: 'a' (confidence=0.20)
```

Confidence on the substituted words is notably unstable across revision
passes, e.g. `'him'` swings 1.00 → 1.00 → 0.78 → 1.00 → 0.12 → 1.00, `'a'`
(before "Bob") swings 1.00 → 0.20 → 1.00 → 0.39 → 1.00 → 0.23 — versus
genuine words like "My"/"name", which stay stable in the 0.85-1.00 range
throughout. Neighboring real words ("short", "hairdo") also dip during the
same revision passes (0.04-0.67), so this isn't a clean, isolated signal.

**Interpretation:**

- **Confirms and sharpens Spike 3's side-finding**: it's not just
  `formattedString()` doing final cleanup; `segments()` and
  `alternativeSubstrings()` never contain "um"/"uh" either, at any point in
  either run. This is a hard blocker at the recognizer/model level, not a
  formatting choice you can route around by reading a lower-level API.
- **Silent dropping isn't the only failure mode**
  Roughly a third of fillers get replaced with a real, plausible-sounding
  word ("uh" → "a", "um" → "him") rather than just vanishing. There's no
  way to distinguish a substituted-filler "a" from a genuine spoken "a"
  using the text alone.
- **Confidence-score volatility is a tentative lead, not a proven signal.**
  Substituted words show much larger swings across revisions than genuine
  words, but nearby real words dip too, so it's noisy rather than a clean
  isolated tell.
- **This changes the project's scope, not just the implementation.**
  `SFSpeechRecognizer` cannot detect "um"/"uh" via any text-based API
  surface, at any level tested. Rather than solve this with a heavier
  architecture change (a cloud STT with disfluency-removal disabled, or a
  specialized local model), the v1 goal is updated: detect filler
  words/phrases that survive as real text (e.g. "like", "so", "actually",
  "basically"), not all disfluencies. "um"/"uh" are out of scope for v1.
- **Real-word survival is already evidenced, not assumed.** "like" appears
  correctly transcribed three separate times across two spikes (Spike 2's
  "I like to eat..." and this spike's two runs) — never dropped, never
  substituted, unlike every "um"/"uh" instance. Every other ordinary word
  spoken across all four spikes transcribed reliably too. The failure mode
  observed is specific to filled-pause disfluencies, not real vocabulary.

**Deferred Decisions:**

- Whether the tracked-word list is a fixed curated default, fully
  user-configurable, or both (default list + user customization) is a
  product decision, not built here.
  - Leaning toward shipping a fixed
    default list first (lowest engineering risk, proves the matching
    pipeline end-to-end), then adding user-configurable words as a fast
    follow, since only the word _source_ changes, not the matching mechanism.
- Acoustic, non-ASR detection of "um"/"uh" (pure DSP signal processing —
  pitch-stability + energy + duration heuristics on the raw audio buffer,
  running alongside `SFSpeechRecognizer` rather than replacing it) is a
  possible v2 expansion, not required for v1. Matches how purpose-built
  filler detectors work in the wild (per Interspeech 2022 benchmark
  research); the raw audio buffer is already available in every spike's
  `tap_callback`, so this wouldn't require reworking Spikes 1-3.
- Word-boundary-aware matching for the matcher itself (e.g. "so" shouldn't
  match inside "also") and how it should handle partial-result revision
  (per Spike 2's finding that words can be silently corrected or retracted
  before finalizing) are implementation decisions for the matcher itself,
  deliberately not designed here.

**Status:** Spike complete. Core question answered with a split result: of the three
words named in the original question ("um", "uh", "like"), "like" survives
reliably as real text across every instance observed, while "um" and "uh"
are unrecoverable at any tested API level (`formattedString()`,
`segments()`, `alternativeSubstrings()`) — confirmed a hard blocker, not a
formatting quirk. This directly shaped the project-level scope decision:
v1 will track real-word fillers only ("like", "so", "actually", "basically",
etc.), not pure disfluency sounds that have no stable word to match against
("um", "oh", "uh", "er"). Acoustic DSP-based detection of those sound-based
fillers is flagged as a possible future v2 expansion, not a v1 requirement.

## Spike 5 Long Session Continuity

**Question:** Does a single `SFSpeechRecognizer` recognition task survive a
long session, or does it terminate after a fixed amount of audio? If it
terminates, does it do so loudly (an error) or silently, and does the audio
engine survive it?

Spikes 1-4 ran for only 5-20 seconds each, while the NFRs require the app to
run continuously in the background over long sessions. Nothing tested so far
spoke to that gap.

**Method:**

1. Copy Spike 2/4's script as the base (permission checks, request +
   recognizer + tap setup, run-loop pump).
2. Strip Spike 4's per-segment logging (`segments()` +
   `alternativeSubstrings()`). That question is answered, and at ~10 lines per
   callback it would bury the signal — and it prints on the main thread, where
   the callback fires (Spike 3), competing with the run loop being measured.
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
  silent-failure mode in this stack, after Spike 1's silent permission
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
  work, deliberately not designed here.

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
