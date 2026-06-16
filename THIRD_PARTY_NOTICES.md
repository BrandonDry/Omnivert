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

Omnivert's installable build also bundles the Python runtime dependencies required to
run the engine and the desktop app, including (non-exhaustive): FastAPI, Starlette,
Uvicorn, pywebview, Trio, pydantic, and the conversion engine's own dependencies such as
magika, onnxruntime, pdfminer.six, pdfplumber, mammoth, python-pptx, openpyxl, xlrd, and
markdownify. Each is distributed under its own permissive open-source license (MIT, BSD,
Apache 2.0, or similar).

The authoritative license and metadata for every installed package is available from its
distribution metadata. To list the bundled packages and their versions in a given
environment:

```powershell
.\.venv\Scripts\python.exe -m pip list
# License of an individual package:
.\.venv\Scripts\python.exe -m pip show <package-name>
```
