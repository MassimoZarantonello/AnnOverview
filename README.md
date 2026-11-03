# AnnOverview

A read-only overview of the annotation rounds: which images each annotator has, how far each image got, and how many
images the next training will take. For one person (the project lead); it reads the shared folder and never writes
to it. No annotator is timed: the page shows no last save and no started or finished dates, only states and counts
per round.

See [docs/design.md](docs/design.md) for the design and every decision.

## Use

The shared folder (one folder per annotator, in the AnnoCell layout) mounted on the Mac, then:

```bash
annoverview <shared folder>
```

The page opens in the browser (http://localhost:8080) and only this computer can reach it; `--share` lets
others on the network open it too. **Refresh** reads the folder again. Three tabs, filterable by slide:

- **Graph**: one round, slides → images (a picture each) → annotators; click a node for its details;
- **Progress**: how much of the model's proposal was kept, round by round, and the models' scores on the test
  regions;
- **Tables**: the rounds (images not started / in progress / complete, how many go into training, closed) and the
  tree of images, by annotator or by round.

Status is as of each annotator's last save in AnnoCell. For a test region, "drawn" only says that cells were drawn:
whether the expert has finished cannot be told from the files.

## How it fits

- [AnnoLoop](../AnnoLoop) (the pipeline) writes the image folders, closes rounds and writes the models' scores;
- [AnnoCell](../AnnoCell) (the annotation tool) saves the corrections and the review (`review.json`) in each folder;
- AnnOverview reads them through `annocell.folder` (so "complete" means the same as for training).

## Development

AnnoCell must sit next to this folder (`../AnnoCell`): `annocell` is installed from there.

```bash
uv sync --extra dev
.venv/bin/python -m pytest
```
