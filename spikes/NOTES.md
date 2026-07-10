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

**Deferred Decisions:**

- Open Question: How should the filler-word matcher handle retracted/revised partial text?

**Question Moving Forward:** Confirm if run-loop-pump is necessary once packaged app.

- During `success, error = audio_engine.startAndReturnError_(None)` `time.sleep()` alone silently drops streaming results in a bare script; needed to actively pump NSRunLoop. It's unverified whether a real packaged app (with its own Cocoa/AppKit event loop already running) needs this workaround at all.

**Status:**
Spike complete, core question answered (streaming confirmed), plus the two carried-forward caveats (run-loop behavior in a packaged app, revision/retraction handling) as open items for later.
