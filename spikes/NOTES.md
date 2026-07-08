# Findings/answers from each spike

<!-- Write 2-3 sentences: what question you asked, what you found, what it means for the design. -->

## Spike 1 Mic Permission + raw audio capture:

**Question:** Can I get a permission prompt to appear, grant it, and print raw
audio sample data to the console for 5 seconds?

**Method:** AVAudioEngine + installTap via PyObjC, printing frame count and
peak amplitude per chunk for 5 seconds.

**Result:** No permission dialog ever appeared. First run produced an all-zero
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

**Interpretation:**

- Permission denial is silent, not an exception. Code that assumes "no error
  = mic is working" would be wrong. Any real app should explicitly check/request
  authorization status rather than assuming.
- The permission prompt/toggle is tied to the _host process_ (e.g. VS Code/Terminal),
  not to this script individually. This is expected for a bare interpreted
  script; a packaged .app with its own Info.plist + NSMicrophoneUsageDescription
  should get its own first-launch prompt tied to its own identity, but this is
  unverified until the app is actually bundled.
- Noticed some peak amplitude values slightly above 1.0 (clipping) when
  speaking close/loud to the mic. No impact on filler-word detection (doesn't
  use amplitude), noting only in case a future feature (e.g. input level meter)
  cares about it.
- Kept the `startAndReturnError_` error-handling branch even though it never
  fired in testing; a denied/not-determined status doesn't cause the engine
  to fail, it just returns silent zeros, so this branch is guarding a
  different failure class entirely (missing input device, session conflicts,
  format mismatches). Untested but cheap to keep.

**Deferred decisions (real app, not this spike):**

- How the UI should react to a denied/not-determined status (e.g. showing a
  message directing the user to System Settings) is UX/state-machine work
  for the app's UI layer; deliberately not built here to keep the spike scoped
  to "can I detect + read permission state," not "how should the app respond
  to it."

**Question moving forward:** Confirm prompt behavior once the app is
packaged as a real .app bundle with Info.plist. Don't assume it'll "just work"
the same way.

**Status:** Core question answered: raw audio capture via AVAudioEngine/PyObjC
works, and permission state is now explicitly observable rather than inferred.

## Spike 2 STT Streaming:
