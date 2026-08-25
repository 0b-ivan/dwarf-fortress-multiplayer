# GHCR image

GitHub Actions builds the open-source runtime image and publishes it to:

```text
ghcr.io/0b-ivan/dwarf-fortress-multiplayer
```

The image intentionally does **not** contain Dwarf Fortress Premium. The purchased
Linux archive remains outside Git/GHCR and is mounted read-only on first start.
The container installs it into the persistent `./data/game` volume and then overlays
the DFHack + DFCapture files from the image.

## Supported architecture

The published image is `linux/amd64` only. Dwarf Fortress 53.16 Linux itself is an
x86-64 binary, and DFHack's Linux build targets x86-64 as well. Publishing a native
`linux/arm64` manifest would therefore be misleading.

Apple Silicon can run the amd64 image through Docker Desktop's x86-64 emulation.

## Pull and start

Place the purchased archive at:

```text
assets/private/dwarf_fortress_53_16_linux.tar.bz2
```

Then:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

On first start, the archive is extracted into `./data/game`. Future image updates
reuse that persistent game directory and refresh only the open-source overlay.

## Tags

The workflow publishes:

- `latest` from the default branch
- `main`
- `sha-<commit>`
- semantic-version tags when pushing `v*` tags

Pull requests build the image without pushing it.

## License boundary

The proprietary Dwarf Fortress archive is neither committed to Git nor embedded in
the GHCR image. Only the project's own packaging plus DFHack/DFCapture build outputs
are published by this pipeline.
