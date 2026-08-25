# filler-words

## Description

Menu bar application that identifies and alerts when filler words (um, uh, etc) are used in speech. Captures mic audio when “on”. Transcribes speech to text and checks the transcription against a fixed list of filler words (e.g ‘um’, ‘uh’, ‘like’, etc). Show lightweight alert when filler word use identified and keep running count of filler words used. Allows users to be aware of their use of filler words and work towards removing those words from speech.

## Features

- ...
- ...

## Local Development

#### Requirements:

- macOS. The app is built directly on Apple's Speech and AVFoundation
  frameworks, so there is no cross-platform path.
- Python 3.12. This is the version the project is pinned to and the one all
  spike measurements were taken on.

#### Typical Development Workflow:

1. Create and activate the virtual environment:

       python3.12 -m venv venv
       source venv/bin/activate

2. Install runtime and development dependencies:

       pip install -r requirements-dev.txt

3. Run the tests:

       pytest

## Contributing

This is a portfolio project, but feedback is welcome! Open an issue or submit a PR.

## Author

Audrey - [GitHub](https://github.com/audreycode6) | [LinkedIn](https://www.linkedin.com/in/audrey-theriault-allaire/)
