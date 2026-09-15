# Reproduce the v12 additions

Download `CAMV-Eval_v12_Reproduction.zip` from [v12-repro-1](https://github.com/JoMinsu-KU/camv-eval/releases/tag/v12-repro-1), keeping it outside the checkout. Its SHA-256 is `1ebc0bee6225516423a8e71d50080567a0c2267b6718a0469bb6a589f22c0fd0`. Python 3.11, NumPy 2.2.6 and SciPy 1.16.2 are the verified numerical versions.

```text
gh release download v12-repro-1 --repo JoMinsu-KU/camv-eval --pattern CAMV-Eval_v12_Reproduction.zip --dir ../v12-assets
python -m pip install -r requirements-v12.txt
python reproduce_v12.py --asset ../v12-assets/CAMV-Eval_v12_Reproduction.zip --output ../v12-replay
```

The output directory must be new and outside this checkout. The command validates the archive and repository manifests, extracts to that directory, then checks all new saved intervals/p-values, regenerates the first outer dataset of each new law, and recalculates 10 CSVs. The original v8 replay commands and assets.json remain available. This does not rerun VLM inference or all original simulations.

For full regeneration of the three new conditions, run the extracted archive's `reproduce.py --regenerate --workers 4 --output <new-directory>` after reading its README. This mode was implemented in the evidence package; the publication preparation validates saved replay and limited regeneration, not a second full Monte Carlo run.

RF conditions match empirical class-count/recording profiles in expectation under a specified score law. They do not validate coverage under the unknown empirical data-generating law. NE_H_C retains pair-permutation symmetry; it does not establish general Type I error control. New J calculations are descriptive and preserve the original four-test family. See [the version map](MANUSCRIPT_VERSION_MAP.md) and `code/v12/PROTOCOL.md`.
