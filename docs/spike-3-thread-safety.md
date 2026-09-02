# Spike 3: Thread Safety

Script: [`spikes/spike3_thread_safety.py`](../spikes/spike3_thread_safety.py)

**Question:** What thread do STT partial-result callbacks actually fire on, and is it safe to mutate UI-facing state directly from there, or does it need explicit main-thread dispatch?

**Method:** [Spike 2](spike-2-stt-streaming.md)'s script, plus an
`NSThread.isMainThread()` log inside the recognition callback and an AppKit
status-item stand-in. Mutated the stand-in directly from the callback, then
re-ran the same mutation wrapped in `dispatch_async` and compared. Watched 3
things each run: the terminal for a crash or warning, the menu bar for whether
the title updated live, and the main-thread log.

> [!NOTE]
> **_Environment issue: `NSStatusItem` creation crashed with a `CGSConnectionByID` assertion_**
>
> Creating an `NSStatusItem` crashed before the callback under test was ever
> reached, with `CGAtomicGet(&is_initialized)` failing inside
> `CGSConnectionByID`. Any real AppKit object needs an `NSApplication` to have
> opened a WindowServer connection first, and a script that imports `AppKit`
> without instantiating one has no such connection. Fixed by calling
> `AppKit.NSApplication.sharedApplication()` before creating the status item; a
> menu-bar-only app also wants
> `setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)`.

**Result:**

Transcript timestamps (main-thread log):

```
Engine started - talk now...
On main thread: True
[+2.17s] Hi
On main thread: True
[+2.61s] Hi I think I
[...]
On main thread: True
[+8.27s] Hi I think I just realize the bug I'm going to be saying oh no
[...]
On main thread: True
[+9.88s] Hi I think I just realize the bug I'm going to be saying oh no I don't know if this is actually
Engine stopped.
```

- The main-thread log: `On main thread: True` on every single callback firing,
  no exceptions.
- Direct mutation: visually confirmed the status-bar title updated live, in sync with
  each partial transcript, no lag or missed updates — direct, unwrapped
  mutation from the callback.

> [!NOTE]
> **_Side finding — filler words missing from transcript_**
>
> "um" never appeared in the transcript despite being spoken several times, and
> "oh" registered only inside a real phrase ("oh no"). Whether the words survive
> below `formattedString()` became
> [Spike 4](spike-4-filler-word-preservation.md).

**Interpretation:**

- **The callback fires on the main thread**, logging `On main thread: True` on
  every callback across both runs.
- **Neither the risk nor the remedy was actually tested.** Because it never left
  the main thread, direct mutation "worked", and the `dispatch_async`-wrapped
  version behaved identically. That shows the wrap costs nothing on a main-thread callback; it
  shows nothing about whether it prevents a crash from a background one.

**Status:** Spike complete. The callback fires on the main thread in this
environment, so direct UI mutation worked and the `dispatch_async` wrap cost
nothing. Carried forward: the `NSApplication` bootstrap any real AppKit object
needs.
