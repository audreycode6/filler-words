# Spike 2: Speech To Text Streaming

Script: [`spikes/spike2_stt_streaming.py`](../spikes/spike2_stt_streaming.py)

**Question:**
Regarding, STT engine logistics, does it support continuous streaming (text arrives incrementally as you speak) or only discrete utterances (you get a full result only after a pause). How does threading look like?:

- If streaming: the matcher can run on partial text as it arrives — genuinely near-real-time.
- If discrete/utterance-based: detection happens in bursts after each pause. Means you should expect speech to be "detected within N seconds of the pause" rather than continuous mid-sentence detection.

**Method:** Permission checks for microphone and speech recognition, then a
streaming recognition request (`setShouldReportPartialResults_(True)`) fed by an
audio tap reusing [Spike 1](spike-1-mic-permission.md)'s engine setup. Spoke a
sentence with a deliberate mid-sentence pause, to see whether text arrived
during the pause or only after it.

> [!NOTE]
> **_Environment issue: speech permission crash tied to the "responsible process"_**
>
> `requestAuthorization_()` crashed with a TCC error demanding
> `NSSpeechRecognitionUsageDescription`. macOS attributes a permission request to
> the application that launched the script rather than to the interpreter, and
> VS Code's Info.plist lacks that key (a known gap). That is also why the
> microphone worked untouched from day one, since VS Code does declare the
> microphone key. Adding the key to Python.app's Info.plist had no effect.
> Running from Terminal.app, which declares both, prompted and granted normally.

**Result:**
Text showed up and stabilized before the pause finished, well ahead of resuming speech, i.e. a clean "streaming, not discrete" result.

Actual transcript timestamps:

```
Engine started - talk now...
[+2.18s] I like
[+2.47s] I like to eat
[+3.18s] I like to eat watermelon
[+3.28s] I like to eat watermelon's
[+3.49s] I like to eat watermelon's
[+6.07s] I like to eat watermelon's I also
[...]
[+7.97s] I like to eat watermelon's I also like to drink watermelon flavored soda
[+8.79s] I like to eat watermelon's I also like to drink watermelon flavored soda one
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

- **Streaming confirmed**: the matcher can run on partial text near-real-time
- **Partial results are provisional, not append-only** — The recognizer revises earlier words as more context arrives.
  - _This is a real design constraint: the matcher can't just naively append/flag words as they first appear; it needs to handle a word it flagged getting silently corrected/retracted a moment later._

**Status:** Spike complete. Recognition streams, delivering text incrementally
rather than in whole utterances, and already-delivered words can be silently
corrected or withdrawn. Revision handling has since been settled by counting a
segment only once the recognizer has finished with it; run-loop behavior in a
packaged app is still open.
