# Spike 2: Speech To Text Streaming

Script: [`spikes/spike2_stt_streaming.py`](../spikes/spike2_stt_streaming.py)


**Question:**
Regarding, STT engine logistics, does it support continuous streaming (text arrives incrementally as you speak) or only discrete utterances (you get a full result only after a pause). How does threading look like?:

- If streaming: your Filler-word matcher can run on partial text as it arrives — genuinely near-real-time.
- If discrete/utterance-based: detection happens in bursts after each pause. Means you should expect speech to be "detected within N seconds of the pause" rather than continuous mid-sentence detection.

**Method:**

1. Status Checks: Mic Permissions Status Check & Speech Recognition Permissions Status Check
2. Create a `SFSpeechAudioBufferRecognitionRequest` instance & call `.setShouldReportPartialResults_(True)` which gives incremental partial results as speech comes in (_blocked initially by a TCC crash requiring `NSSpeechRecognitionUsageDescription` --see Environment Issue below_)

3. Create an `SFSpeechRecognizer` instance
4. Start a recognition task with request
5. Initialize engine and install tap (from [spike 1](spike-1-mic-permission.md)) which will take in `tap_callback`.
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

