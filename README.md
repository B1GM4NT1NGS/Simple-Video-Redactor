# Simple Video Redactor

A local Windows desktop app for drawing black redactions over video, or drawing boxes around the areas you want to keep visible and blacking out everything else.

If this software helped you, [buy me a coffee](https://buymeacoffee.com/bigzz).

## Download and run

1. Download the source ZIP from **Code → Download ZIP**, or use the source ZIP on the Releases page.
2. Extract it to a folder on your computer.
3. Install [Python 3.11 or newer for Windows](https://www.python.org/downloads/windows/).
4. Double-click **Run Simple Video Redactor.cmd**. On first launch it creates a local environment and installs the dependencies from the Python package registry. Later launches use those installed dependencies.

For macOS/Linux or manual setup:

```sh
python -m venv .venv
# Activate your environment, then:
python -m pip install -r requirements.txt
python simple_video_redactor.py
```

The interface is developed and tested on Windows. Other platforms are untested. The GitHub download contains source files, not a compiled executable. Browser and security software decisions vary; no download format can guarantee acceptance.

## Using the app

The app always starts with an empty video screen. Click **Import video** to select footage.

- **Keep boxes visible** is the default: everything outside active boxes becomes black.
- **Hide boxes** blacks out areas inside active boxes.
- Pause and drag to draw a box. Select it to move it, or drag its bottom-right corner to resize.
- Set each box's start/end times in seconds if it should apply to only part of the video.
- Press **Play** for a clean redaction preview. Uncheck clean preview to edit against the original footage.
- Optionally remove audio.
- Click **Export redacted MP4**. When asked whether to crop first, choose **No** for an ordinary export or **Yes** to open the crop-and-trim editor.
- In the crop editor, drag any yellow corner to crop the picture, or drag inside the crop rectangle to move it. Drag the yellow timeline handles to shorten the beginning/end. Click the thumbnail strip to scrub, or enter precise start/end seconds. **Play selection** previews that time range. **Apply & export** opens the save dialog.

Cropping applies after redaction. Trimming keeps each box's timing aligned with the original footage. Exported redactions are burned into the video pixels. Original files are preserved.

## Formats

Common import formats include **MP4, AVI, MKV, MOV, WMV, WebM, M4V, MPG/MPEG, MTS/M2TS, TS, 3GP, FLV, VOB, OGV and ASF**. The included FFmpeg engine prepares a playable preview. Actual support depends on the codec, file integrity and encryption; DRM-protected files are unsupported. Exports use **MP4 with H.264 video and AAC audio**.

## Limits and privacy

Boxes stay fixed in position; automatic motion tracking is not included. Review the entire exported video before sharing it. Audio remains unless you choose to remove it. Rotation metadata is ignored consistently in preview and export. Video processing stays on your computer; importing/exporting never uploads footage. First-time dependency installation needs Internet access. The coffee button opens its website only when clicked.

## Optional portable build

Developers can build a single Windows executable locally:

```sh
python -m pip install -r requirements.txt pyinstaller
python build_portable.py
```

The result appears in `dist/`. The build includes the video engine and Qt runtime. Compiled executables are not uploaded to this repository.

## Tests

Run `python -m unittest discover -s tests`. The integration check generates synthetic footage and verifies both redaction modes, crop dimensions, trimmed duration, audio retention and redaction timing after trimming.

## License

The application source is MIT licensed. Python, PySide6/Qt, FFmpeg and other dependencies have their own licenses. See [THIRD_PARTY.md](THIRD_PARTY.md), especially before redistributing a compiled build.
