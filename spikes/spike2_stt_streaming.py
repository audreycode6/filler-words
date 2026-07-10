"""
Spike 2 — spike2_stt_streaming.py
Steps, in order:

Copy the working audio engine + tap setup from Spike 1
  (don't refactor it into something shared yet — just copy-paste, this is a spike)
Import Speech (SFSpeechRecognizer, SFSpeechAudioBufferRecognitionRequest)
Create an SFSpeechAudioBufferRecognitionRequest
Create an SFSpeechRecognizer and start a recognition task with that request, with a callback for results
Instead of printing raw audio in the tap callback (like Spike 1 did), append each buffer to the recognition request
In the recognition result callback, print the transcribed text and a timestamp, every time it fires
Speak one full sentence out loud with a deliberate pause in the middle
Watch the console output

Definition of done: you can look at your printed log and answer
— did text show up before the pause finished, or only after you stopped talking entirely?
"""

import AVFoundation
import Foundation
import time
import Speech

# Mic Permissions Status Check
mic_status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
    AVFoundation.AVMediaTypeAudio
)
if mic_status == 0:
    print(
        "Mic permission status: not determined (0) -- user hasn't been asked for permission yet."
    )
elif mic_status == 1:
    print("Mic permission status: restricted (1) -- access is restricted by something.")
elif mic_status == 2:
    print(
        "Mic permission status: denied (2) -- user or system settings have explicitely said no."
    )
elif mic_status == 3:
    print("Mic permission status: authorized (3) -- good to go!")
else:
    print(f"Mic permission status: unknown ({mic_status})")

# Speech Recognition Permissions Status Check
"""
Speech recognition has its own separate authorization system,
distinct from microphone access. SFSpeechRecognizer has a class method
requestAuthorization 
(with a callback reporting authorized/denied/restricted/notDetermined, 
same shape as the mic one).
"""


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

# speech_recognition_request.setShouldReportPartialResults_()
# is what determines streaming vs. discrete:
#     - Set to True, it should give you incremental partial
#     results as speech comes in
#     - Set to False, you'd only get a final result
#     after a pause


# Create an SFSpeechRecognizer instance
speech_recognizer = Speech.SFSpeechRecognizer.alloc().init()


def recognition_result_callback(result, error):
    if error is not None:
        print(f"Recognition error: {error}")
        return
    if result is not None:
        print(
            f"[+{time.time() - start_time:.2f}s] {result.bestTranscription().formattedString()}"
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


# Install tap on Bus 0
input_node.installTapOnBus_bufferSize_format_block_(0, 1024, input_format, tap_callback)

start_time = time.time()
success, error = audio_engine.startAndReturnError_(None)
if not success:
    print("Failed to start engine:", error)
else:
    print("Engine started - talk now...")

    # time to speak full sentence with mid-sentence pause
    #   time.sleep() alone doesnt work here;
    #   the run loop needs to be pumped for streaming results to be delivered.
    end_time = time.time() + 10
    run_loop = Foundation.NSRunLoop.currentRunLoop()
    while time.time() < end_time:
        run_loop.runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.1))

    audio_engine.stop()
    print("Engine stopped.")
