# Continuous integration and container delivery

The GitHub Actions workflow in `.github/workflows/tests.yml` checks every push
and pull request before it can become a classroom build. It has four stages:

1. Python 3.11 and 3.12 both run the complete pytest suite. CI installs a
   RISC-V assembler so the generated `.S` teaching files are assembled and
   compared with generated C. Python and JavaScript syntax are checked first.
2. Pull requests receive a dependency review. A newly introduced dependency
   with a high or critical known vulnerability fails the check. If the
   repository's Dependency graph is off, the job audits `requirements.lock`
   with `pip-audit` instead.
3. Docker builds the same full toolchain image used in class. Several pretend
   students compile real ESP32-C6 and QEMU PRG32 cartridges concurrently, then
   CI starts the web service and checks its discovery document.
4. After all checks pass, pushes to `main` and version tags publish a
   multi-platform `linux/amd64` and `linux/arm64` image to GitHub Container
   Registry. The image receives a signed provenance attestation.

Pull requests never receive package-write or identity-token permissions and
never publish an image. Superseded branch builds are cancelled; version-tag
builds are allowed to finish.

## Image names and versions

The registry path is the lowercase repository name:

```text
ghcr.io/riscv-prg32/prg32-construction-kit
```

Tags have these meanings:

| Git event | Published tags |
| --- | --- |
| Push to `main` | `edge`, plus immutable `sha-<commit>` |
| Push tag `v1.2.3` | `1.2.3`, `1.2`, `latest`, plus immutable `sha-<commit>` |
| Pull request or other branch | no image is published |

Use `edge` to test the newest accepted change. Use a numbered tag for a
classroom term so every machine runs the same toolchain:

```bash
docker pull ghcr.io/riscv-prg32/prg32-construction-kit:1.2.3
docker run --rm -p 5090:5090 \
  -e PRG32_ADMIN_PASSWORD='change-this-password' \
  -v "$PWD/data:/data" \
  ghcr.io/riscv-prg32/prg32-construction-kit:1.2.3
```

The package must be public for anonymous pulls. If the GitHub organization
keeps it private, sign in first with a token that can read packages:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u GITHUB_USER --password-stdin
```

## Making a release

1. Confirm the `main` workflow is green.
2. Create and push a semantic version tag:

   ```bash
   git tag -a v1.2.3 -m "PRG32-Construction-Kit 1.2.3"
   git push origin v1.2.3
   ```

3. Wait for **CI and container delivery** to finish.
4. In the workflow summary, copy the published digest and use the numbered
   image tag in the classroom deployment.

No server credentials are built into the image. Runtime secrets such as
`PRG32_ADMIN_PASSWORD`, database credentials and SSO secrets remain deployment
settings.

## Repository settings

For protected `main`, require these checks before merging:

- `Python 3.11 tests`
- `Python 3.12 tests`
- `Dependency review`
- `Toolchain container and real cartridges`

GitHub Actions must have permission to create packages. The publish job grants
only `packages: write`, `attestations: write` and `id-token: write`; other jobs
remain read-only. Dependabot checks GitHub Actions, Python requirements and the
Docker base image each week.
