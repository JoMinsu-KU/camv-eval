# Maintaining a verified release

`MANIFEST.json` covers the shipped Git tree, excluding the manifest itself. `assets.json` fixes every release ZIP's bytes and SHA-256; nested archive manifests fix the earlier components. `.gitattributes` prevents automatic line-ending changes. A checksum detects a changed file, not an authenticated external signature.

The scientific sources and expected numbers belong to frozen versions. When changing scientific code, create a new version and document the change, regenerate the appropriate outputs, and validate it independently. Do not edit expected results merely to make a replay pass.

For reviewed documentation-only changes, regenerate the repository manifest with:

```sh
python tools/update_manifest.py
python reproduce.py --mode quick --output ../camv-doc-check
```

The updater excludes `.git`, virtual environments, caches, and downloaded archives. It must not be used to conceal an unreviewed scientific or release-asset change. This preparation's full replay was performed on the exact code and data hashes recorded in `provenance/verification.json`. A changed wrapper or scientific input needs a corresponding new verification record. Never replace an already published numerical asset with different bytes under the same release identity.
