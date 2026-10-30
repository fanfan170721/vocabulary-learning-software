# Dependencies and assets

- Python runtime: [Python Software Foundation License](https://docs.python.org/3/license.html).
- PySide6 / Qt: use the [open-source license terms supplied with the dependencies](https://doc.qt.io/qtforpython-6/licenses.html). Distribution should retain the licenses and required notices for Qt, PySide, Shiboken, and the Qt components used, and use dynamic libraries. Review the components actually included in this version before public distribution.
- LGPL/GPL and Python license texts are kept in `vocabulary_app/resources/licenses` and distributed with the bundle. Corresponding source for Qt 6.12 and PySide6 6.12.0 is available from the [Qt releases](https://download.qt.io/official_releases/qt/) and [Qt for Python releases](https://download.qt.io/official_releases/QtForPython/pyside6/). The bundle retains dynamic library files so compatible libraries can be replaced under their licenses.
- PyInstaller build tool: [GPL with an application distribution exception](https://pyinstaller.org/en/stable/license.html).
- Pronunciation uses installed Windows SAPI voices. System voice resources are not bundled or redistributed. A missing accent is reported as unavailable.
- The original 180 seed entries and additional selected ECDICT entries have separate source records. Pinned ECDICT revision `ab22ad36302cafc6349a050e2b60894855208055` uses the upstream MIT license; the full text is retained in `resources/licenses/ECDICT-MIT.txt`. See CONTENT.md for the actual scope and pinned source hashes. Project code and original seed content licenses are separate decisions; all resources are not collectively labeled MIT.
- The interface uses white backgrounds, blue/pink emphasis, and whitespace, with standard widgets and programmatically drawn shapes. It does not copy third-party brand marks, accounts, promotional images, or character assets.

Development references: official Qt for Python installation/API documentation and official PyInstaller build/runtime documentation. Development tools and dependencies do not require paid services. The app has no advertising, payments, or subscriptions.
