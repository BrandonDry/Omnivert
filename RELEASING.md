# Releasing Omnivert

Release repository: `BrandonDry/Omnivert`.

## Manual App Release

1. Bump `src/omnivert/app_version.py`.
2. Confirm `src/omnivert/build_info.py` points at `BrandonDry/Omnivert` for the
   private release repo.
3. Run the local checks from `README.md` at least through frontend build, web asset copy,
   backend smoke, and wheel build.
4. Commit the change.
5. Tag the commit with `vX.Y.Z`.
6. Push the tag.

The `Build Windows Release` workflow builds the frontend, copies it into the Python
package, freezes the app with PyInstaller, compiles the Inno Setup installer, and uploads
`Setup.exe` plus the wheel to the GitHub Release.

The workflow must still be validated on GitHub for repository permissions, branch rules,
and release asset upload permissions before relying on it for public distribution.

## Automated Conversion Engine Releases

`Watch Conversion Engine` runs on a schedule and checks PyPI for a newer conversion engine
version than the one pinned in `pyproject.toml`.

When a newer engine exists, `Guarded Engine Update`:

- pins the new conversion engine version in `pyproject.toml`
- bumps the Omnivert patch version
- stamps the release repo into `build_info.py`
- runs frontend build/lint
- installs the updated Python package
- runs backend import checks
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
