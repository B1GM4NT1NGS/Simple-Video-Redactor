# Simple Video Redactor

A free Windows desktop app for permanently redacting video, tracking moving subjects, and cropping or trimming footage. All video processing stays on your computer.

## Download and run

[Download Simple Video Redactor v1.0.0](https://github.com/B1GM4NT1NGS/Simple-Video-Redactor/releases/latest).

1. Download the source ZIP and extract it.
2. Install [Python 3.11 or newer for Windows](https://www.python.org/downloads/windows/).
3. Double-click **Run Simple Video Redactor.cmd**. The first launch installs the required dependencies; later launches use the local environment.

The download contains source files, not a compiled executable. The app opens with an empty screen ready to import your video.

## Features

- **Hide boxes:** black out selected areas of the footage.
- **Keep boxes visible:** keep selected areas visible and black out everything outside them.
- **Track subjects:** make one or more boxes follow moving subjects. Mix tracked and fixed boxes.
- **Film strip preview:** drag to scrub through the video; drag the yellow end handles to shorten it.
- **Crop before export:** drag the crop frame's corners to remove unwanted edges.
- **Box controls:** numbered cards show tracking status and timing, with a bin beside each box.
- **Clear all changes:** reset the edit while keeping the imported video open.
- **MP4 export:** burn redactions into the video, with optional audio removal.

## How to use it

Import a video, pause on a clear frame, and draw a box. Choose **Hide boxes** or **Keep boxes visible**. Select a box and click **Track selected subject** if it should follow movement. Repeat for additional subjects.

Play or scrub to review. To correct a track, pause, move or resize its box, then track again. Changing a box or its time range clears its previous track. Use the bin to remove a box, or **Clear all changes** to start again.

Use the film strip's yellow handles to set the video length. Click **Export redacted MP4** and choose whether to crop the picture before saving. Your original video is preserved.

## Supported formats

Common imports include MP4, AVI, MKV, MOV, WMV, WebM, M4V, MPEG, MTS/M2TS, TS, 3GP, FLV, VOB, OGV and ASF. Support depends on the file's codec and integrity; DRM-protected footage is unsupported. Exports use MP4 with H.264 video and AAC audio.

## Privacy and review

Footage stays local. Initial dependency installation requires Internet access; external links open only when clicked. See the [privacy policy](PRIVACY.md).

Tracking uses rectangular boxes and can drift when subjects become hidden, cross each other or move abruptly. Review the whole exported video before sharing it. Audio remains unless removed. Rotation metadata is ignored consistently in preview and export.

## Build from source

```sh
python -m pip install -r requirements.txt pyinstaller
python build_portable.py
```

The portable Windows executable appears in `dist/`. Current builds are unsigned; see the [code signing policy](CODE_SIGNING.md). Run `python -m unittest discover -s tests` for the video-processing integration checks.

## License and support

The application source is MIT licensed. Dependencies have their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). Report problems through [GitHub issues](https://github.com/B1GM4NT1NGS/Simple-Video-Redactor/issues).

If this software helped you, [buy me a coffee](https://buymeacoffee.com/bigzz).
