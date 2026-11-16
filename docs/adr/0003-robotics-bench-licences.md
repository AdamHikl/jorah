# ADR 0003: licences outside the allowlist for the robotics bench

**Decision:** accept these for personal use, and check them again before anything is published or
sold. Adam, 2026-11-16: "A: list and accept".

**Scope:** only the Python tools the robotics bench installs root-owned on the PC
(`deploy/jorah-bench/requirements-pio.txt` for PlatformIO, `requirements-cad.txt` for build123d;
`docs/runbooks/robotics-bench.md`). Project runs use them as tools; Jorah's own code never imports
them, and nothing of them is redistributed. `scripts/check-licenses.sh` accepts these licences only
for packages that appear in the bench's lock files and in no other manifest: the same package in a
service's dependencies still needs an allowed licence.

| Package | Licence | Where it comes from | Why it's acceptable |
|---|---|---|---|
| `chardet` 5.2.0 (PlatformIO) | LGPL-2.0-or-later | PyPI metadata and classifier | Used unmodified as a library by a tool; LGPL asks nothing of a user who doesn't redistribute it |
| OpenCascade, bundled in `cadquery-ocp-novtk` 8.0.1.1.0 (build123d's CAD kernel) | LGPL-2.1-only WITH OCCT-exception-1.0 | The wheel declares Apache-2.0 for the OCP bindings (CadQuery/OCP `LICENSE`); the OpenCascade libraries inside it are under OCCT's `LICENSE_LGPL_21.txt` and `OCCT_LGPL_EXCEPTION.txt` (Open-Cascade-SAS/OCCT) | As for chardet. The exception only relaxes LGPL further. Listed as `Apache-2.0 AND LGPL-2.1-only WITH OCCT-exception-1.0` |
| `typing_extensions` 4.16.0 | PSF-2.0 | PyPI `license_expression` | Permissive, Python's own licence |
| `pyelftools` 0.33 (PlatformIO) | Unlicense (public domain), and MIT for the `construct` library it bundles | sdist `LICENSE` (Unlicense text); `construct`'s licence from `elftools/construct/LICENSE` in eliben/pyelftools, MIT (the sdist itself doesn't ship that file) | Public domain and MIT. Listed as `Unlicense AND MIT` |
| `pillow` 13.0.0 (build123d) | MIT-CMU | PyPI `license_expression` | Permissive, MIT-style (HPND) |

**Packages with no licence in their metadata**, checked in their source distributions on 2026-11-16.
All three have one; none is unlicensed:

| Package | Licence | Where found |
|---|---|---|
| `anytree` 2.13.0 | Apache-2.0 | `anytree-2.13.0/LICENSE` in the sdist (full Apache 2.0 text) and `license = "Apache-2.0"` in its `pyproject.toml`; repo github.com/c0fec0de/anytree |
| `bd_materials` 0.2.5 | Apache-2.0 | `bd_materials-0.2.5/LICENSE` in the sdist (full Apache 2.0 text); repo github.com/bernhard-42/bd_materials |
| `ocpsvg` 0.7.0 | Apache-2.0 | `ocpsvg-0.7.0/LICENSE` in the sdist (full Apache 2.0 text); PyPI names no repository |

**Packages whose metadata only says "BSD"** were read from the licence file in their wheels: all
BSD-3-Clause (a "neither the name" clause), except `semantic-version` (BSD-2-Clause). `packaging` is
`Apache-2.0 OR BSD-2-Clause`; it's listed as Apache-2.0, the option taken.

**Also bundled, not listed per package:** the binary wheels of `numpy`, `scipy` and `scikit-learn`
carry compiled runtime libraries (OpenBLAS, BSD-3-Clause; libgfortran, libquadmath and libgomp under
GPL-3.0-or-later WITH GCC-exception-3.1 or LGPL). `config/licenses.tsv` records each package's own
declared licence, as for `numpy` since ADR 0001. Fine for personal use; part of the re-check before
anything is published or sold.

**Re-check when:** the bench's lock files change (a new package or a licence change fails
`just licenses` until it's listed), or before anything built with the bench is published or sold.

`just licenses` reads `config/licenses.tsv`, which lists all 74 bench packages with their licences.
