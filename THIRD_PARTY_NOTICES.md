# Third-party notices

This file lists third-party software distributed with Mebel Pro's backend
container image, beyond the Python/JavaScript packages declared in
`backend/pyproject.toml` / `backend/uv.lock` and `web/package.json` /
`web/pnpm-lock.yaml`.

## PackingSolver

- **Project:** [PackingSolver](https://github.com/fontanf/packingsolver)
- **Author:** Florian Fontan
- **Upstream URL:** https://github.com/fontanf/packingsolver
- **Pinned commit:** `6915ff627a70ee0d71f5adca81f0ecbb0d0579e4`
- **License:** MIT

Mebel Pro's backend image builds the `packingsolver_rectangleguillotine`
executable from this pinned commit and installs it as a local subprocess used
by the `cutting-engine` package's PackingSolver provider (see
`docs/ref/features/cutting.md`). Upstream source is never vendored into this
repository; the container build fetches, checksum-verifies, and compiles it —
see `backend/Dockerfile`, stage `packingsolver-builder`. A copy of the license
below is also installed in the image at
`/usr/share/licenses/packingsolver/LICENSE`.

### License text

```
MIT License

Copyright (c) 2020 Florian Fontan

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
