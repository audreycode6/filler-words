# Spike 3: Thread Safety

Script: [`spikes/spike3_thread_safety.py`](../spikes/spike3_thread_safety.py)


**Question:** What thread do STT partial-result callbacks actually fire on, and is it safe to mutate UI-facing state directly from there, or does it need explicit main-thread dispatch?

**Method:**

1. Copy [Spike 2](spike-2-stt-streaming.md)'s script as the base (permission checks, request +
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
> **Motivates [Spike 4](spike-4-filler-word-preservation.md):** does `SFTranscription.segments()` preserve filler
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

