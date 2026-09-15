# Original data and model sources

The numerical replay needs only the included score projections, grouping/label metadata, and saved simulation arrays. It downloads no source images or model weights. Source acquisition below is for inspecting the original materials or preparing a separately specified full inference run.

| Source | Frozen identity used in this study | Access |
|---|---|---|
| RLBench-Fail test dataset | Hugging Face revision `2a07643ffdcd9b6ac694f866fe6fb59814fca51b` | [Dataset repository](https://huggingface.co/datasets/paulpacaud/rlbenchfail_test_dataset) |
| UR5-Fail test dataset | Hugging Face revision `fedfcb3346b92f6a2bfeb14dc254635c9a5013f1` | [Dataset repository](https://huggingface.co/datasets/paulpacaud/ur5fail_test_dataset) |
| REASSEMBLE | Original TU Wien record, version 1.0.0, DOI `10.48436/0ewrv-8cb44` | [Original dataset record](https://researchdata.tuwien.ac.at/records/0ewrv-8cb44), [original loader code](https://github.com/TUWIEN-ASL/REASSEMBLE) |
| SmolVLM-Instruct | Model revision `81cd9a775a4d644f2faf4e7becff4559b46b14c7` | [Pinned model card](https://huggingface.co/HuggingFaceTB/SmolVLM-Instruct/blob/81cd9a775a4d644f2faf4e7becff4559b46b14c7/README.md) |

The RLBench-Fail and UR5-Fail dataset cards identify Apache-2.0 licensing; the pinned SmolVLM card also identifies Apache-2.0. This is source attribution, not an extension of the repository's MIT license to those materials. Consult each source's current terms and the frozen provenance before acquisition. Historical InternVL/Qwen model identifiers, revisions, processors, prompts, and image metadata are recorded under the original v2 archive's `package/provenance/model-and-data-records/`.

The frozen REASSEMBLE record identifies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) in its rights metadata. The record is the original multimodal dataset. This study uses its defined grasp-closure endpoint and official split/membership information; it does not equate that endpoint with retention in the other cohorts. The archived cohort construction and sample/group membership files identify the actual subset. No REASSEMBLE images, audio, HDF5 recordings, or weights are redistributed here.

For an image-level study, use the dataset repositories' Files pages at the frozen revisions listed above, and obtain REASSEMBLE's data and official splits from the original record. Inspect the archived model/data provenance before reproducing image selection, endpoint construction, prompting, and scoring. Acquisition and a new model execution are separate from this package's verified numerical commands. The included simulation laws, seeds and namespace records specify synthetic data generation.

The associated manuscript's 37 reference entries are preserved in [references.bib](references.bib). Dataset/model citations remain due to the original creators. No DOI for CAMV-Eval itself is invented in this package; the DOI above belongs to REASSEMBLE.
