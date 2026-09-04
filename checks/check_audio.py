"""Stream from the microphone for a while and report whether recognition held up.

    python checks/check_audio.py [seconds]

Prints the permission state before anything starts, every transcript as it
arrives, and a verdict reporting the longest gap between transcripts.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import Foundation

from audio import (
    AUTHORIZED,
    RUN_LOOP_SLICE_SECONDS,
    UNDETERMINED,
    OnDeviceUnavailable,
    SpeechPipeline,
    authorization_state,
    request_authorization,
)

DEFAULT_CHECK_SECONDS = 180

# A gap this long between transcripts, while speech continues, is reported as a
# stall. Above the quiet spell before a rollover, measured at 8.5s in a
# 181-second run, and under the ~61s at which the server path stops.
CONTINUITY_GAP_SECONDS = 20

# How long the permission prompts may go unanswered before the check gives up.
PROMPT_TIMEOUT_SECONDS = 60


def _settled_state():
    """Ask for whichever permission is undetermined, and report what came back."""
    print("Asking. Answer the prompts...")
    decided = []
    request_authorization(decided.append)

    # Pump a plain run loop, since the pipeline's does not exist yet.
    run_loop = Foundation.NSRunLoop.currentRunLoop()
    deadline = time.monotonic() + PROMPT_TIMEOUT_SECONDS
    while not decided and time.monotonic() < deadline:
        run_loop.runUntilDate_(
            Foundation.NSDate.dateWithTimeIntervalSinceNow_(RUN_LOOP_SLICE_SECONDS)
        )

    return decided[0] if decided else authorization_state()


def run(seconds):
    state = authorization_state()
    print(f"Authorization: {state}")

    if state == UNDETERMINED:
        state = _settled_state()
        print(f"Authorization: {state}")

    if state != AUTHORIZED:
        print(
            "Refusing to start. Nothing was recorded and no engine was run --\n"
            "a run without permission returns silence, due to no audio input.\n"
            "Grant access in System Settings > Privacy & Security, under both\n"
            "Microphone and Speech Recognition."
        )
        return 1

    started_at = time.monotonic()
    arrivals = []

    def show(transcript):
        arrivals.append(time.monotonic())
        print(f"[+{time.monotonic() - started_at:7.2f}s] {transcript}")

    def complain(error):
        print(f"[+{time.monotonic() - started_at:7.2f}s] ERROR {error}")

    def stalled(device_name):
        elapsed = time.monotonic() - started_at
        source = device_name or "the microphone"
        print(f"[+{elapsed:7.2f}s] STALLED -- no audio from {source}")
        pipeline.stop()

    pipeline = SpeechPipeline(
        show, on_error=complain, on_stalled=stalled, pump_run_loop=True
    )

    try:
        pipeline.start()
    except OnDeviceUnavailable as unavailable:
        print(f"Refusing to start: {unavailable}")
        return 2

    print(f"Listening for {seconds}s -- talk now, and keep talking.")
    try:
        pipeline.pump(seconds)
    except KeyboardInterrupt:
        # Report on the partial run rather than unwinding past the summary,
        # which is the only output the check produces.
        print("\nInterrupted -- reporting on the partial run.")
    finally:
        pipeline.stop()

    elapsed = time.monotonic() - started_at
    gaps = [
        later - earlier for earlier, later in zip([started_at] + arrivals, arrivals)
    ]
    longest_gap = max(gaps, default=elapsed)

    print(
        f"\nSummary: ran {elapsed:.1f}s | transcripts={len(arrivals)} | "
        f"longest gap={longest_gap:.1f}s | buffers={pipeline.buffers_appended} | "
        f"restarts={pipeline.tasks_started - 1}"
    )
    if not arrivals:
        print("FAIL: no transcripts ever arrived.")
        return 1
    if longest_gap > CONTINUITY_GAP_SECONDS:
        print(
            f"FAIL: recognition went quiet for {longest_gap:.1f}s, "
            f"over the {CONTINUITY_GAP_SECONDS}s this is checking for."
        )
        return 1

    print("OK: transcripts arrived continuously for the whole run.")
    return 0


if __name__ == "__main__":
    requested = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CHECK_SECONDS
    sys.exit(run(requested))
