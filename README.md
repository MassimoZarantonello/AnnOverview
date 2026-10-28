# AnnOverview

A read-only overview of the annotation rounds: which ROIs each annotator has, how far they got, what they saved
last, and how many ROIs the next training will take. For one person (the project lead); it reads the shared folder
and never writes to it.

See [docs/design.md](docs/design.md) for the design and every decision.

## Use

The shared folder (one folder per annotator, in the AnnoCell layout) mounted on the Mac, then:

```bash
annoverview <shared folder>
```

The page opens in the browser (http://localhost:8080) and only this computer can reach it; `--share` lets
others on the network open it too. **Refresh** reads the folder again. Three parts: the rounds
(ROIs not started / in progress / complete, how many go into training, closed), the last save of each annotator,
and the tree of ROIs, by annotator or by round, filterable by slide.

Status is as of each annotator's last save: an annotator who stopped and one whose laptop is offline look the same.
For a test region, "drawn" only says that cells were drawn: whether the expert has finished cannot be told from the
files.

## How it fits

- [AnnoLoop](../AnnoLoop) (the pipeline) writes the ROI folders and closes rounds;
- [AnnoCell](../AnnoCell) (the annotation tool) saves the corrections and the review in each folder;
- AnnOverview reads them through `annocell.folder` (so "complete" means the same as for training).

## Development

AnnoCell must sit next to this folder (`../AnnoCell`): `annocell` is installed from there.

```bash
uv sync --extra dev
.venv/bin/python -m pytest
```
