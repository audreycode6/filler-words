# verbal-habits

## Description

Menu bar app for tracking word usage — helping to remove undesirable
vocabulary from speech. Turn it on and it listens, transcribes your speech on
device, and keeps a running count of every word on your tracked list. Each use
raises a lightweight alert as it happens, and the session ends with a summary
of the totals.

## Features

- ...
- ...

## Local Development

#### Requirements:

- macOS. The app is built directly on Apple's Speech and AVFoundation
  frameworks, so there is no cross-platform path.
- Python 3.12. This is the version the project is pinned to and the one all
  spike measurements were taken on.
- Terminal.app. An editor's integrated terminal may not declare
  `NSSpeechRecognitionUsageDescription`, and macOS ends the process without a
  message when the launching application is missing it.
  > [!NOTE]
  > Packaging the app as its own signed application removes this.

Those spike measurements, and the design decisions they settled, are written up
in [`docs/`](docs/README.md).

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
