# Third-Party Notices

Omnivert is distributed with third-party open-source software. The required copyright
and permission notices for that software are reproduced below.

---

## Microsoft MarkItDown (conversion engine)

Omnivert bundles and runs **MarkItDown**, the document-to-Markdown conversion engine
created by Microsoft Corporation.

- Project: https://github.com/microsoft/markitdown
- Package: https://pypi.org/project/markitdown/
- License: MIT

```
MIT License

    Copyright (c) Microsoft Corporation.

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
```

> Omnivert is an independent project and is not affiliated with, endorsed by, or
> sponsored by Microsoft. "MarkItDown" and "Microsoft" are used only to accurately
> describe the origin of the bundled engine.

---

## Other bundled open-source components

The installable build bundles a Python runtime and the libraries the engine and the desktop
app need: more than 90 Python distributions, plus a compiled frontend. Most are permissive
(MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, 0BSD, MIT-CMU, PSF-2.0). Some are not, so
those are named individually below rather than covered by a blanket claim.

### Where the licence text is in your install

For a default per-user install the application directory is:

```text
%LOCALAPPDATA%\Programs\Omnivert\
```

Licence files live under its `_internal` subdirectory:

- `_internal\LICENSE`, `_internal\NOTICE` and `_internal\THIRD_PARTY_NOTICES.md` are
  Omnivert's own Apache-2.0 licence, its attribution notice, and this file.
- `_internal\<package>-<version>.dist-info\licenses\` holds the licence text for packages
  that publish one in modern metadata. Older packages put it directly in
  `_internal\<package>-<version>.dist-info\` instead.
- `_internal\onnxruntime\LICENSE` and `_internal\onnxruntime\ThirdPartyNotices.txt` cover
  onnxruntime and everything compiled into it, including the full MPL 2.0 text.
- `_internal\speechrecognition-<version>.dist-info\licenses\` holds both
  SpeechRecognition's own BSD licence and the GPLv2 text for the bundled FLAC binaries.

Not every bundled component ships its licence file in that tree. Ones whose text is absent
include magika and flatbuffers (both Apache-2.0), pywebview, fastapi, starlette, uvicorn,
anyio, h11, trio, PyYAML, pythonnet, psutil and pypdfium2. Each is permissively licensed and
its name and version are recorded in the bundled metadata; the authoritative text is the
LICENSE file in that project's own release. Collecting every licence file into the build so
the install is self-contained is tracked work, not a claim made here.

To list packages and licences in a development environment:

```powershell
.\.venv\Scripts\python.exe -m pip list
.\.venv\Scripts\python.exe -m pip show <package-name>
```

### Components that are not permissively licensed

**certifi (Mozilla Public License 2.0).** certifi supplies the CA root bundle extracted from
Mozilla NSS. MPL-2.0 is weak, file-level copyleft: it does not reach Omnivert's own code and
does not require Omnivert's source to be published, but it does require anyone distributing
the binary to keep the notice intact and to make the source of the MPL-covered files
available. The notice ships at `_internal\certifi-<version>.dist-info\licenses\LICENSE`.
Note that file is the short MPL notice block rather than the full licence text, which is at
https://mozilla.org/MPL/2.0/. certifi is bundled unmodified, so the upstream release at
https://github.com/certifi/python-certifi satisfies the source requirement. Anyone who
modifies certifi must publish the modified files under MPL-2.0.

**FLAC command-line encoder (GNU General Public License, version 2).** SpeechRecognition is
BSD-3-Clause but bundles prebuilt `flac` executables, and the Windows one at
`_internal\speech_recognition\flac-win32.exe` is used by the audio transcription path.
These are standalone executables Omnivert runs as child processes, not code linked into
Omnivert, so the GPL does not extend to Omnivert's own code. GPLv2 does require anyone
redistributing the binaries to provide the corresponding source, or a written offer for it.
They are unmodified upstream builds; source is at https://github.com/xiph/flac.

**Eigen (Mozilla Public License 2.0), compiled into onnxruntime.** onnxruntime itself is MIT,
but the prebuilt `onnxruntime.dll` has Eigen compiled in. Same notice-and-source obligation as
certifi's. Microsoft's own `_internal\onnxruntime\ThirdPartyNotices.txt` ships with the app
and carries the full MPL-2.0 text plus the component list. Eigen source is at
https://gitlab.com/libeigen/eigen.

**Microsoft Edge WebView2 (Microsoft SDK licence terms, not open source).** The desktop window
is rendered by WebView2. pywebview (BSD-3-Clause) bundles Microsoft's interop assemblies,
which ship at `_internal\webview\lib\Microsoft.Web.WebView2.Core.dll`,
`Microsoft.Web.WebView2.WinForms.dll` and
`_internal\webview\lib\runtimes\<arch>\native\WebView2Loader.dll`. These are proprietary
Microsoft components, redistributed under the Microsoft Software License Terms for the
Microsoft Edge WebView2 SDK, which permit redistribution alongside an application. No source
is available for them and no Microsoft licence text ships in the bundle; the terms are
published with the SDK at https://developer.microsoft.com/microsoft-edge/webview2/.

**GCC runtime library (GPL-3.0-or-later with the GCC Runtime Library Exception), inside
NumPy.** `_internal\numpy.libs\libscipy_openblas*.dll` is statically linked against files
compiled with GCC. The GCC Runtime Library Exception exists precisely so programs compiled
with GCC can be distributed under any licence, so this places no copyleft obligation on
Omnivert. NumPy's full notice is at
`_internal\numpy-<version>.dist-info\licenses\LICENSE.txt`.

None of the above requires Omnivert's own source to be released, and none of it conflicts
with distributing Omnivert under Apache-2.0.

Pillow's licence file reproduces the GPLv2 text, but it appears there as the alternative arm
of FreeType's dual FTL/GPLv2 licence, and Pillow ships under the FTL arm, which is
permissive. The same file's xz section references GPLv2 and LGPLv2.1 for xz command-line
scripts and build files, none of which are bundled.

PyInstaller, which freezes the application, is GPL-2.0-or-later with a Bootloader Exception
covering `bootloader/` and `PyInstaller/loader`. Only the bootloader reaches the shipped
executable, and the exception is written to allow exactly that. Up to and including 0.1.5 the
build also embedded 23 of PyInstaller's build-time modules, which the exception does not
cover; `packaging/app.spec` now excludes them and the exclusion is checked before release.

### Permissively licensed components

- **MIT:** markitdown, pydantic, pydantic-core, urllib3, attrs, beautifulsoup4, soupsieve,
  openpyxl, python-pptx, pdfminer.six, pdfplumber, markdownify, PyYAML, fastapi, anyio, h11,
  onnxruntime, pythonnet, clr_loader, watchfiles, httptools, jiter, six, pydub, coloredlogs,
  humanfriendly, charset-normalizer, azure-core, azure-identity,
  azure-ai-documentintelligence, azure-ai-contentunderstanding, msal, PyJWT, et_xmlfile,
  bottle, proxy_tools, setuptools.
- **BSD (2-Clause and 3-Clause):** lxml, pandas, starlette, uvicorn, click, idna, httpx2,
  httpcore2, websockets, pywebview, mammoth, cobble, olefile, xlrd, xlsxwriter, sympy, mpmath,
  python-dotenv, psutil, pycparser, isodate, colorama, pyreadline3, pywin32-ctypes, and
  SpeechRecognition's own code.
- **Apache-2.0:** magika, openai, requests, flatbuffers, tzdata, python-multipart,
  sortedcontainers.
- **Dual permissive:** trio, outcome and sniffio (MIT or Apache-2.0); cryptography
  (Apache-2.0 or BSD-3-Clause); python-dateutil (Apache-2.0 or BSD-3-Clause); packaging
  (Apache-2.0 or BSD-2-Clause); pypdfium2 (BSD-3-Clause or Apache-2.0, its bundled PDFium
  binary carrying its own permissive upstream notices for FreeType, libjpeg-turbo, libpng,
  libtiff, zlib, ICU, Little CMS and others).
- **Other permissive:** Pillow (MIT-CMU), typing_extensions and defusedxml (Python Software
  Foundation licence), cffi (MIT-0), numpy (BSD-3-Clause, with vendored 0BSD, MIT, Zlib and
  CC0-1.0 components each listed in its own LICENSE.txt).

### Bundled frontend

The user interface is a compiled React application served from `_internal\web\`. Build
minification strips licence banners from the bundle, so the libraries are acknowledged here
instead. Everything shipped in the frontend is permissive: React and React DOM, Radix UI,
react-markdown, remark-gfm and the unified/micromark/mdast ecosystem, sonner, clsx and
tailwind-merge (MIT); tslib (0BSD); lucide-react and @ungap/structured-clone (ISC);
class-variance-authority (Apache-2.0). Build-time tooling (Vite, TypeScript, ESLint, Tailwind
and its lightningcss transformer) is not shipped, so its licences do not apply to the
distributed application.
