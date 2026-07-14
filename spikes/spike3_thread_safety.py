import AppKit
import AVFoundation
import dispatch
import Foundation
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
time.sleep(6)  # give callback time to run before engine setup.

# Create a SFSpeechAudioBufferRecognitionRequest instance
speech_recognition_request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
speech_recognition_request.setShouldReportPartialResults_(True)


# Create an SFSpeechRecognizer instance
speech_recognizer = Speech.SFSpeechRecognizer.alloc().init()


def recognition_result_callback(result, error):
    if error is not None:
        print(f"Recognition error: {error}")
        return
    if result is not None:
        text = result.bestTranscription().formattedString()
        print(f"On main thread: {Foundation.NSThread.isMainThread()}")
        print(f"[+{time.time() - start_time:.2f}s] {text}")
        dispatch.dispatch_async(
            dispatch.dispatch_get_main_queue(), lambda: update_status_title(text)
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
    """
    audio engine calls automatically every time a
    chunk of audio is ready

    - buffer is an AVAudioPCMBuffer obj holding audio samples
    - when is an AVAudioTime timestamp saying when that chunk occurred
    """
    speech_recognition_request.appendAudioPCMBuffer_(buffer)


def update_status_title(text):
    status_item.button().setTitle_(text)


# creating any real AppKit UI object requires an active NSApplication instance
#   to have established a connection to the WindowServer first
app = AppKit.NSApplication.sharedApplication()
# Create the UI stand-in
status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
    AppKit.NSVariableStatusItemLength
)
status_item.button().setTitle_("🎤 waiting...")


# Install tap on Bus 0
input_node.installTapOnBus_bufferSize_format_block_(0, 1024, input_format, tap_callback)

start_time = time.time()
success, error = audio_engine.startAndReturnError_(None)
if not success:
    print("Failed to start engine:", error)
else:
    print("Engine started - talk now...")

    # time to speak full sentence with mid-sentence pause
    end_time = time.time() + 10
    run_loop = Foundation.NSRunLoop.currentRunLoop()
    while time.time() < end_time:
        run_loop.runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.1))

    audio_engine.stop()
    print("Engine stopped.")
