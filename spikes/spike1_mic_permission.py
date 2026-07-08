import AVFoundation
import time

# Mic Permissions Status Check
status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
    AVFoundation.AVMediaTypeAudio
)
if status == 0:
    print(
        "Mic permission status: not determined (0) -- user hasn't been asked for permission yet."
    )
elif status == 1:
    print("Mic permission status: restricted (1) -- access is restricted by something.")
elif status == 2:
    print(
        "Mic permission status: denied (2) -- user or system settings have explicitely said no."
    )
elif status == 3:
    print("Mic permission status: authorized (3) -- good to go!")
else:
    print(f"Mic permission status: unknown ({status})")


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
    audio_frames_length = buffer.frameLength()
    channel_data = buffer.floatChannelData()[0]  # pointer to 1st channel's sample
    samples = [channel_data[i] for i in range(audio_frames_length)]
    max_val = max(abs(s) for s in samples) if samples else 0.0
    print(
        f"frames (chunk size) = {audio_frames_length} | max (peak amplitude) = {max_val:.4f}"
    )


# Install tap on Bus 0
input_node.installTapOnBus_bufferSize_format_block_(0, 1024, input_format, tap_callback)

success, error = audio_engine.startAndReturnError_(None)
if not success:
    print("Failed to start engine:", error)
else:
    print("Engine started - talk now...")
    time.sleep(5)
    audio_engine.stop()
    print("Engine stopped.")
