import AVFoundation
import Foundation
import resource
import time
import Speech

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

# Create a SFSpeechAudioBufferRecognitionRequest instance
speech_recognition_request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
speech_recognition_request.setShouldReportPartialResults_(True)

# Create an SFSpeechRecognizer instance
speech_recognizer = Speech.SFSpeechRecognizer.alloc().init()

callback_count = 0
buffer_count = 0
last_callback_time = None


def recognition_result_callback(result, error):
    global callback_count, last_callback_time

    now = time.time()
    last_callback_time = now
    callback_count += 1

    if error is not None:
        print(
            f"[+{now - start_time:7.2f}s] ERROR "
            f"domain={error.domain()} code={error.code()} "
            f":: {error.localizedDescription()}"
        )
        return
    if result is not None:
        text = result.bestTranscription().formattedString()
        print(
            f"[+{now - start_time:7.2f}s] "
            f"#{callback_count:<4} "
            f"final={str(result.isFinal()):<5} "
            f"chars={len(text):<5} "
            f"...{text[-45:]}"
        )


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

start_time = time.time()
success, error = audio_engine.startAndReturnError_(None)
if not success:
    print("Failed to start engine:", error)
else:
    print("Engine started - talk now...")

    end_time = time.time() + 300  # 5 min
    run_loop = Foundation.NSRunLoop.currentRunLoop()
    last_heartbeat = time.time()
    warned = False

    while time.time() < end_time:
        run_loop.runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.1))
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

    # Headline result: when did callbacks stop relative to audio still flowing?
    print(
        f"SUMMARY: ran {time.time() - start_time:.1f}s | "
        f"buffers={buffer_count} | callbacks={callback_count}"
    )
    if last_callback_time is not None:
        print(f"         last callback at +{last_callback_time - start_time:.2f}s")
    else:
        print("         no callbacks ever fired")
