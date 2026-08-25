"""The Apple framework modules the app imports must be installed.

Guards the pinned set in requirements.txt: if a needed package is ever
dropped from it, this fails here rather than at the microphone.
"""


def test_pyobjc_frameworks_are_installed():
    import AVFoundation  # AVAudioEngine, AVCaptureDevice
    import Foundation    # NSRunLoop, NSDate
    import Speech        # SFSpeechRecognizer
    import AppKit        # NSStatusBar
    import dispatch      # dispatch_async
