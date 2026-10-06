# Third-party components

The MIT license covers this application's own source code only.

- [Python](https://www.python.org/about/legal/) uses the Python Software Foundation license.
- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html) is available under LGPLv3/GPLv3 or commercial licenses, subject to component-specific terms.
- [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) uses BSD-2-Clause for its Python wrapper.
- [FFmpeg](https://ffmpeg.org/legal.html) licensing depends on its build options. Builds including libx264 are GPL builds. Check the chosen binary's `-L` and `-buildconf` output and provide the required notices, corresponding source and applicable replacement/relinking rights when redistributing binaries.
- [PyInstaller](https://pyinstaller.org/en/stable/license.html) is GPL licensed with a bootloader exception permitting application distribution.

This repository distributes application source and dependency references. It does not distribute compiled third-party binaries or a precompiled executable.

## Subject tracking

OpenCV / opencv-contrib-python-headless 4.13.0.92 (Apache-2.0, with separately licensed bundled components): https://github.com/opencv/opencv-python and https://github.com/opencv/opencv . NumPy uses the BSD-3-Clause license: https://numpy.org/doc/stable/license.html . The headless package avoids bundling a second GUI toolkit. Refer to the wheel license files for bundled dependency notices when redistributing binaries.
