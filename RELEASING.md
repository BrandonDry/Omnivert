# Releasing Omnivert

Release repository: `BrandonDry/Omnivert`.

## Manual App Release

1. Bump `src/omnivert/app_version.py`.
2. Confirm `src/omnivert/build_info.py` points at `BrandonDry/Omnivert` for the
   release repo.
3. Move the `## [Unreleased]` entries in `CHANGELOG.md` under a `## [X.Y.Z] - YYYY-MM-DD`
   heading and update the compare links at the bottom of the file.
4. Run the local checks from `README.md`: `python -m pytest -q`, `tests\engine_smoke.py`,
   frontend build and lint, web asset copy, and the wheel build.
5. Commit the change.
6. Tag the commit with `vX.Y.Z`.
7. Push the tag.

The `Build Windows Release` workflow builds the frontend, copies it into the Python
package, freezes the app with PyInstaller, compiles the Inno Setup installer, and uploads
`Setup.exe` plus the wheel to the GitHub Release.

The release is created as a **draft**. Assets are attached but nothing reaches users until
a maintainer opens the draft on GitHub and clicks **Publish**. That click is the human
approval gate, and it is the same gate the automated engine bump goes through.

This chain has been validated end to end on `BrandonDry/Omnivert` (freeze, installer
compile, silent per-user install, launch, conversion, and update over an existing install).

## Automated Conversion Engine Releases

`Watch Conversion Engine` runs on a schedule and checks PyPI for a newer conversion engine
version than the one pinned in `pyproject.toml`.

When a newer engine exists, `Guarded Engine Update`:

- pins the new conversion engine version in `pyproject.toml`
- bumps the Omnivert patch version
- stamps the release repo into `build_info.py`
- runs frontend build/lint
- installs the updated Python package with its test extra
- runs backend import checks
- runs the `pytest` suite (catches an engine that changed its accepted extensions or its
  constructor kwargs, which no conversion failure would reveal)
- runs conversion smoke tests
- builds a wheel
- opens a bot PR
- merges it and tags the new Omnivert version when allowed

Pushing the tag triggers the normal release workflow. If any check fails, no release is
published and the workflow opens an issue.

## Notes

- Frozen Windows builds cannot pip-update the engine. Engine updates reach users through
  new Omnivert releases.
- Unsigned installers may trigger Windows SmartScreen until code signing is added.
- Before shipping to users, manually verify PyInstaller freeze, Inno Setup compile,
  `Setup.exe` install/launch, conversion from the installed app, and update over an
  existing install.
- Omnivert is a fresh app identity. It uses its own installer AppId and settings directory;
  previous app installs/settings are not migrated.
