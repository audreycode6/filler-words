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
# Successfully getting audio
Mic permission status: authorized -- good to go!
Engine started - talk now...
frames (chunk size) = 4800 | max (peak amplitude) = 0.0048
frames (chunk size) = 4800 | max (peak amplitude) = 0.1352
frames (chunk size) = 4800 | max (peak amplitude) = 0.7670
[...]
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
[...]
Engine stopped.
```

**Interpretation:**

- **Permission denial is silent, not an exception.** _Any real app should explicitly check/request
  authorization status._
- **The permission prompt/toggle is tied to the _host process_ (e.g. VS Code/Terminal),
  not to this script individually.**

> [!NOTE]
> **Kept the `startAndReturnError_` error-handling branch even though it never
> fired**, since it guards failures a permission denial never causes: a missing
> input device, a session conflict, a format mismatch.

**Status:** Core question answered: raw audio capture via AVAudioEngine/PyObjC
works, and permission state is now explicitly observable rather than inferred.
