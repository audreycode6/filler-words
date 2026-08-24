"""
Two questions Spike 5 left open:
  1. Does the ~60s recognition task cap survive requiresOnDeviceRecognition?
  2. Are partial-result revisions confined to the tail of the transcript?
"""

import AVFoundation
import Foundation
import resource
import sys
import time
import Speech

ON_DEVICE = True  # flip to False for the server-mode comparison run
DURATION = 300  # seconds

# Read aloud, the same way, in both modes. Seeded with "like" as a filler (x2),
# "like" as a comparative/verb, plus "so", "um" and "uh". Long enough that the
# front of the transcript is well settled while the tail is still moving.
PASSAGE = """
So I was thinking about the project the other day, and, um, the thing that
keeps coming back to me is how much of it depends on the transcript staying
put once it has been written. I like the idea of counting words as they
settle rather than waiting for the end. It works like a ratchet, uh, where
nothing behind the cursor ever moves again. And that is, like, the whole
assumption, so it seems worth checking properly before building on top of it.
Anyway, I am going to keep talking past this point so the recording runs well
past the sixty second mark with speech still in progress.
"""


def find_revision(previous, current):
    """Compare consecutive partial transcripts.

    Returns None when `current` simply extends `previous` (append-only, the
    assumption stable-prefix counting rests on). Otherwise returns the
    divergence: where it started, how far back from the old tail it reached,
    and both spans.
    """
    if current.startswith(previous):
        return None

    # How many characters the two transcripts agree on from the start, which
    # is also the index of the first character where they differ.
    diverged_at = 0
    for previous_char, current_char in zip(previous, current):
        if previous_char != current_char:
            break
        diverged_at += 1

    # Count a partially-rewritten word as fully touched: walk back to the start
    # of the word the divergence landed inside. The word before the divergence
    # is only intact when both sides agree it ended there, e.g. "wonder" ->
    # "wondered" diverges on a space but still rewrites the word before it.
    preceding_word_intact = previous[diverged_at] == " " and (
        diverged_at >= len(current) or current[diverged_at] == " "
    )
    first_rewritten_word_at = (
        diverged_at
        if preceding_word_intact
        else previous.rfind(" ", 0, diverged_at) + 1
    )

    return {
        "index": diverged_at,
        "chars_back": len(previous) - diverged_at,
        "words_back": len(previous[first_rewritten_word_at:].split()),
        "was": previous[diverged_at:],
        "now": current[diverged_at:],
    }


def selftest():
    """Exercise find_revision without a mic."""
    cases = [
        ("pure append", "hello world", "hello world today", None),
        ("empty start", "", "new task text", None),
        ("tail rewrite", "the cat sat on the mat", "the cat sat on the map", (1, 1)),
        ("front rewrite", "the cat sat on the mat", "a cat sat on the mat", (22, 6)),
        ("mid rewrite", "i wonder for like a", "i wondered for like a", (11, 4)),
        ("truncation", "hello world", "hello", (6, 1)),
        ("space boundary", "a b c", "a b", (2, 1)),
    ]
    failures = 0
    for name, prev, curr, expected in cases:
        got = find_revision(prev, curr)
        if expected is None:
            ok = got is None
            detail = "None" if ok else got
        else:
            ok = got is not None and (got["chars_back"], got["words_back"]) == expected
            detail = None if got is None else (got["chars_back"], got["words_back"])
        print(
            f"  {'PASS' if ok else 'FAIL'}  {name:<14} expected={expected} got={detail}"
        )
        if not ok:
            failures += 1
    print(f"selftest: {len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if "--selftest" in sys.argv:
    sys.exit(selftest())


MODE_LABEL = "ON-DEVICE" if ON_DEVICE else "SERVER"
print(f"Mode: {MODE_LABEL} | duration: {DURATION}s")

# Mic Permissions Status Check
mic_status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
    AVFoundation.AVMediaTypeAudio
)
if mic_status == 0:
    print(
        "Mic permission status: not determined -- user hasn't been asked for permission yet."
    )
elif mic_status == 1:
    print("Mic permission status: restricted -- access is restricted by something.")
elif mic_status == 2:
    print(
        "Mic permission status: denied -- user or system settings have explicitely said no."
    )
elif mic_status == 3:
    print("Mic permission status: authorized -- good to go!")
else:
    print(f"Mic permission status: unknown ({mic_status})")


# Speech Recognition Permissions Status Check
def speech_auth_callback(status):
    if status == 0:
        print("Speech Recognition Status: not determined.")
    elif status == 1:
        print("Speech Recognition Status: restricted.")
    elif status == 2:
        print("Speech Recognition Status: denied.")
    else:
        print("Speech Recognition Status: authorized.")


Speech.SFSpeechRecognizer.requestAuthorization_(speech_auth_callback)
print("Waiting for you to respond to any permission dialog...")
time.sleep(1)

# Create an SFSpeechRecognizer instance
speech_recognizer = Speech.SFSpeechRecognizer.alloc().init()

supports_on_device = speech_recognizer.supportsOnDeviceRecognition()
print(f"supportsOnDeviceRecognition(): {supports_on_device}")

# Fail loudly rather than silently falling back to the server.
if ON_DEVICE and not supports_on_device:
    print(
        "ABORT: on-device recognition requested but unsupported for this locale.\n"
        "       Refusing to fall back to server recognition -- the result would\n"
        "       be indistinguishable from a real on-device run."
    )
    sys.exit(2)

# Create a SFSpeechAudioBufferRecognitionRequest instance
speech_recognition_request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
speech_recognition_request.setShouldReportPartialResults_(True)
if ON_DEVICE:
    speech_recognition_request.setRequiresOnDeviceRecognition_(True)
print(
    "requiresOnDeviceRecognition(): "
    f"{speech_recognition_request.requiresOnDeviceRecognition()}"
)

callback_count = 0
buffer_count = 0
last_callback_time = None
prev_text = ""
last_text = ""
revisions = 0
max_chars_back = 0
max_words_back = 0
first_final_at = None


def recognition_result_callback(result, error):
    global callback_count, last_callback_time, prev_text, last_text
    global revisions, max_chars_back, max_words_back, first_final_at

    now = time.time()
    last_callback_time = now
    callback_count += 1
    stamp = f"[+{now - start_time:7.2f}s]"

    if error is not None:
        print(
            f"{stamp} ERROR "
            f"domain={error.domain()} code={error.code()} "
            f":: {error.localizedDescription()}"
        )
        return
    if result is None:
        return

    text = result.bestTranscription().formattedString()
    is_final = result.isFinal()
    print(
        f"{stamp} "
        f"#{callback_count:<4} "
        f"final={str(is_final):<5} "
        f"chars={len(text):<5}"
    )
    print(f"           full: {text}")

    revision = find_revision(prev_text, text)
    if revision is not None:
        revisions += 1
        max_chars_back = max(max_chars_back, revision["chars_back"])
        max_words_back = max(max_words_back, revision["words_back"])
        print(
            f"{stamp} !! REVISION at char {revision['index']} "
            f"({revision['chars_back']} chars / {revision['words_back']} words "
            f"back from tail)"
        )
        print(f"           was: {revision['was']!r}")
        print(f"           now: {revision['now']!r}")

    last_text = text
    if is_final:
        if first_final_at is None:
            first_final_at = now
        # A new task starts from an empty transcript. That reset is not a
        # revision, so don't let the restart boundary be counted as one.
        prev_text = ""
    else:
        prev_text = text


# Start a recognition task with request
recognition_task = speech_recognizer.recognitionTaskWithRequest_resultHandler_(
    speech_recognition_request, recognition_result_callback
)

# Initialize the engine and get input node
audio_engine = AVFoundation.AVAudioEngine.alloc().init()
input_node = audio_engine.inputNode()

# Get the output format of the input node (Bus 0)
input_format = input_node.inputFormatForBus_(0)


def tap_callback(buffer, when):
    global buffer_count
    buffer_count += 1
    speech_recognition_request.appendAudioPCMBuffer_(buffer)


# Install tap on Bus 0
input_node.installTapOnBus_bufferSize_format_block_(0, 1024, input_format, tap_callback)

print("\n--- READ THIS ALOUD, THE SAME WAY IN BOTH MODES ---")
print(PASSAGE.strip())
print("--- then keep talking past 60s, mid-sentence ---\n")

start_time = time.time()
success, error = audio_engine.startAndReturnError_(None)
if not success:
    print("Failed to start engine:", error)
else:
    print("Engine started - talk now...")

    end_time = time.time() + DURATION
    run_loop = Foundation.NSRunLoop.currentRunLoop()
    last_heartbeat = time.time()
    warned = False

    interrupted = False

    while time.time() < end_time:
        # Recognition callbacks are delivered by the Cocoa run loop, so the
        # main thread has to run it. A plain sleep() would produce a run with
        # no callbacks and no error. Pumped in 0.1s slices so the checks below
        # get a turn between them.
        try:
            run_loop.runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.1))
        except KeyboardInterrupt:
            # Break rather than propagate: the SUMMARY below is the run's only
            # output, and unwinding out of this block skips it. The INTERRUPTED
            # label keeps a partial run from reading as a complete one.
            print("\nInterrupted -- reporting on the partial run.")
            interrupted = True
            break

        now = time.time()

        # Silence detector: callbacks stopped while audio keeps flowing?
        if last_callback_time is not None and now - last_callback_time > 10:
            if not warned:
                print(
                    f"[+{now - start_time:7.2f}s] !! NO CALLBACKS for "
                    f"{now - last_callback_time:.1f}s "
                    f"(buffers={buffer_count}, callbacks={callback_count})"
                )
                warned = True
        else:
            warned = False

        # Heartbeat every 30s
        if now - last_heartbeat >= 30:
            rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
            print(
                f"[+{now - start_time:7.2f}s] -- heartbeat: "
                f"buffers={buffer_count} callbacks={callback_count} "
                f"maxrss={rss_mb:.1f}MB"
            )
            last_heartbeat = now

    audio_engine.stop()
    print("Engine stopped.")

    # Q1: did recognition outlive the ~60s cap Spike 5 measured?
    print(
        f"SUMMARY [{MODE_LABEL}{' INTERRUPTED' if interrupted else ''}]: "
        f"ran {time.time() - start_time:.1f}s | "
        f"buffers={buffer_count} | callbacks={callback_count}"
    )
    if last_callback_time is not None:
        print(f"         last callback at +{last_callback_time - start_time:.2f}s")
    else:
        print("         no callbacks ever fired")
    if first_final_at is not None:
        print(f"         first isFinal at +{first_final_at - start_time:.2f}s")
    else:
        print("         isFinal never fired")

    # Q2: how far behind the tail did the recognizer ever rewrite?
    print(
        f"         revisions={revisions} "
        f"max_chars_back={max_chars_back} "
        f"max_words_back={max_words_back}"
    )

    # Q3: the transcript to diff word-for-word against the other mode.
    print("--- FINAL TRANSCRIPT ---")
    print(last_text)
    print("--- END FINAL TRANSCRIPT ---")
