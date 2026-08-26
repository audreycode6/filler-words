# Spike 1: Mic Permission + Raw Audio Capture

Script: [`spikes/spike1_mic_permission.py`](../spikes/spike1_mic_permission.py)


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

