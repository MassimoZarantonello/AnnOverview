# AnnOverview: an overview of the annotation rounds

Status: built and tested on fake folders, not yet on a real round (revised 2026-11-03). Points marked *to decide* are
still open. The current state and the open issues, in short: [../AnnOverview.md](../AnnOverview.md) (local, not in
the repository).

## Goal

See at a glance where the annotation of the project stands: which images each annotator has, which are done, and how
many the next training will take; and whether the model gets better from round to round. For Massimo only; nobody
else runs it.

AnnOverview **only reads**. It never writes to the shared folder, so it can be left open and refreshed at any time
without risk to an annotation.

**No annotator is timed** (AnnoLoop D8: no monitoring of annotators). The page shows states and counts per round; it
never shows when an annotator last saved, started or finished an image, or how long they took.

## Three repositories, three roles

AnnoLoop is the project's pipeline, started as a copy of macroseg (which stays as it was).

| Repository | Role | Writes |
|---|---|---|
| [AnnoLoop](../../AnnoLoop) | the pipeline: assigns the images, segments them with the model of the round, writes each image folder for its annotator, closes a round, trains on the corrections, scores the models | the image folders (`image.tif`, `start_masks.tif`, `compare/`, `annotation.json`), `closed_on`, `scores/<model>.json` |
| [AnnoCell](../../AnnoCell) (public) | the annotation tool: the annotator opens an image folder, corrects it, the tool saves into the same folder; it does not know about AnnoLoop | `masks.tif`, `cells.csv`, `review.json` (the review); never `annotation.json` |
| AnnOverview (private) | the overview: reads the whole tree | nothing |

There is no live connection between them: they share files on the network drive. The contract is AnnoCell's folder
format (`annocell.folder`): AnnoLoop writes it, AnnoCell reads and updates it, AnnOverview reads it. AnnOverview
depends on `annocell` core (numpy and tifffile only, no napari) and reads through it, so the field names and the
layout are defined in one place: if AnnoCell changes its format, AnnOverview picks it up or flags the folder on
`format_version` (newer or older than the `annocell` installed), never shows wrong counts silently. It does not
depend on AnnoLoop.

Which images go to whom stays in AnnoLoop: it needs the stores, the model and the round's settings file.

## The shared folder

On fs4: `smb://fs4.irc.ugent.be/experimental/exp/units/u_csc/private/massimoz/<annotation root>`, mounted on the
annotators' laptops (Windows, through the VPN from home) and on Massimo's Mac, where AnnOverview reads it.

### Layout

```
<root>/
  alice/                      one folder per annotator: the only one the annotator opens
    round_03/<image>/         an image folder in the AnnoCell layout
    round_02/<image>/         an earlier round: closed, read-only in AnnoCell
  bob/
    round_03/<image>/
  carla/
    test/<image>/             a test region: drawn from scratch by one expert annotator
  scores/<model>.json         each model's score on the test regions (AnnoLoop)
```

Annotators get **whole images**, with every channel raw (AnnoLoop D1), 3–4 per annotator per round, 5 annotators in
round 1 (AnnoLoop D2). The format's own word for an image folder is still "ROI" (`annocell.folder.rois`, `Roi`); in
this repository's code `RoiStatus` is one image folder.

Annotator first, then round: each annotator has exactly one folder, their entry point. Opening their own folder
opens the latest round that is not closed. Rejected: `round_NN/<annotator>/<image>/`, which groups by round but gives
each annotator one folder per round to choose from, and so a chance to open the wrong one.

- **Annotator names**: short, lowercase, letters, digits and `-` (e.g. `alice`), the same as folder name and in
  `annotation.json`; AnnoLoop checks every name against one list, so a typo is an error, not a new annotator.
- **One annotator per image** for now: training takes one mask per image, and blending several annotators
  (AnnoLoop `docs/concurrent_annotations.md`) is not built. Shared images (AnnoLoop O1) are open; the graph already
  draws an image given to several annotators as one node.
- Annotators work directly on the network drive, each only in their own folder (by trust, not permissions).

### Opening the wrong round

An annotator could open an earlier round by mistake and change annotations that were already used for training. So:

- when a round is over, AnnoLoop **closes** it: it writes `closed_on` (a date) into the `annotation.json` of every
  image of that round;
- AnnoCell opens a closed image **read-only** (and stops saving one it had open): the annotator can look but not
  edit, and the panel says "round 2: closed";
- `annocell <annotator folder>` (or Open folder on it) opens the latest round that is not closed;
- folders are never moved when a round closes (moving files on a network drive while someone has them open is
  asking for trouble), and AnnOverview keeps the whole history of rounds.

### What AnnOverview reads

Folder format 2 of `annocell.folder`: one writer per file. `annotation.json` is written by AnnoLoop only,
`review.json` by AnnoCell only.

| Field | File, written by | Use |
|---|---|---|
| `format_version` | `annotation.json`, AnnoLoop at export | a folder newer or older than the installed `annocell` is shown as a problem ("export it again"), not read |
| `annotator`, `round` | `annotation.json`, AnnoLoop at export | the tree (also given by the folders; the record is the reference) |
| `source` (slide) | `annotation.json`, AnnoLoop at export | the slide filter and the graph's slide column |
| `mode` (`train` / `test`) | `annotation.json`, AnnoLoop at export | test regions apart |
| `visible_channels`, `colours` | `annotation.json`, AnnoLoop at export | the picture of each image in the graph |
| `closed_on` | `annotation.json`, AnnoLoop when a round ends | closed rounds |
| `cells`, `ok`, `unreviewed`, `proposed` (kept), `edited`, `drawn`, `deleted` | `review.json`, AnnoCell at every save (`read_review`) | state, and the corrections of complete images |
| `saved_at` | `review.json`, AnnoCell | only whether AnnoCell ever saved (not started otherwise); the time itself is not shown |
| `model`, `round`, `regions[*]["AP@…"]` | `scores/<model>.json`, AnnoLoop (`read_scores`) | the Progress tab |

Not read: `region`, `exported_on`, `image`, `start_segmentation`, `compare`, the review's `started_at`,
`completed_at`, `start_cells`, `ok_hand` / `ok_bulk` and `macrophages`.

A tree walker in `annocell.folder` (`rois`) lists the image folders under the root with annotator and round, for
AnnoLoop and AnnOverview alike.

### No timing of annotators

Decided: **no session times, and no per-annotator times on the page**. How long an image takes depends too much on
the case (and on interruptions) to say anything, and checking up on colleagues is not the point (AnnoLoop D8). The
model's progress is measured on the masks instead: how much of the proposal was kept (Progress tab), and the scores
on the test regions.

AnnoCell's review still records `started_at` (the first save) and `completed_at` (the save at which no cell was left
unreviewed). AnnOverview does not read them. Whether AnnoCell should keep writing them is AnnoCell's decision.

## What AnnOverview shows

A local web page (NiceGUI), started with `annoverview <root>` on the Mac, read again with a **refresh button** (no
automatic polling). Listens on this computer only; `--share` opens it to the network.

- **Status of an image**: not started (AnnoCell never saved it), in progress (*x* of *n* cells checked), complete (no
  cell unreviewed: done), closed (round over). A test region with cells is "drawn". A folder that cannot be read
  (half synced, other format) is shown as a problem.
- **Graph** of one round: slides → images (a picture each, framed in the colour of its state) → annotators, dragged
  and zoomed with the mouse; a click shows the details of a node, and of a complete image its corrections (kept,
  edited, deleted, drawn new).
- **Per round**: images assigned, by state, going into training (see Rounds), cells checked, closed.
- **Tree**: annotator → round → image, and the same by round → annotator → image, filterable by slide.
- **Progress**: per round, over the complete images, the share of the proposal's cells kept, edited and deleted (it
  should grow if the model improves); per model, the mean AP on the test regions.
- **Slide map** (later): each slide with its images and test regions, coloured by status, over a thumbnail that
  AnnoLoop writes once per slide (`slides/<slide>.png`).

## Rounds

One round = one model iteration: every image of round *N* starts from the segmentation of the model trained after
round *N − 1*. **Massimo decides when a round is over**; AnnoLoop then closes it and trains. Not every image has to be
finished: training takes the complete ones only, an unfinished image is left out (and stays visible in AnnOverview).
So one slow or stuck image never holds back the next model.

**Training and scoring (AnnoLoop, decided)**:

- **No validation split, from the first round**: every tile of every complete image goes into training. Training cuts
  each image into 512 x 512 tiles: Cellpose-SAM sees one random 256 x 256 crop per image and epoch, so a whole image
  as one training image would be seen a tiny part at a time; as 512 px tiles, every tile is visited each epoch.
- **Fixed training settings** (epochs, learning rate, ...): Cellpose's usual fine-tuning settings, kept the same
  every round, never changed after looking at a test score (the score would stop being independent).
- **Scored on the test regions only** (see Test regions).

**Going into training** = complete (at least one cell, none unreviewed). Decided by one function of
`annocell.folder` (`is_complete`), which AnnoLoop's training and AnnOverview both call, so the count AnnOverview
shows per round is the number of images the next training will take. AnnOverview counts images and cells, not tiles.

**Images per annotator per round**: 3–4 (AnnoLoop D2). Which images go in which round is AnnoLoop's (O3).

**"Mark all in view as OK"** (Shift+O in AnnoCell) is allowed (AnnoLoop D6). AnnoCell now records how each cell
became OK (`ok_by`: hand / bulk; counts `ok_hand`, `ok_bulk` in the review). *To decide*: whether the Progress tab
shows the bulk share, or leaves bulk-OK'd cells out of "kept", which otherwise flatters the model (AnnoLoop O2).

## Test regions

Drawn from scratch by one expert annotator, never given to anyone else and never used for training; in that
annotator's folder (`<annotator>/test/<image>/`). AnnoLoop deals with the test set later (AnnoLoop D12), possibly a
smaller image annotated from scratch. AnnOverview already shows the test regions (as "drawn") and the scores
AnnoLoop writes for them; nothing here depends on how many there are.

## Sprints

1. **The format and the layout**: done.
   1. AnnoCell format: the layout helpers, the optional fields, closing an image, the tree walker, `is_complete`;
      format 2 (`review.json`, `ok_by`): done.
   2. AnnoLoop: export into the new layout; closing a round; training on complete images without a validation
      split; scoring on the test regions: done. Assigning images from the round's settings file: to build there.
   3. AnnoCell tool: annotator and round in the panel; closed images read-only; own folder opens the latest open
      round; saving that survives the network drive: done.
   4. AnnOverview: the tree with status, refresh button, graph, Progress tab: done. Tried on a real round exported
      by AnnoLoop: **not yet**.
2. ~~History~~ (started / finished per image, last save per annotator): built, then removed from the page (no
   timing of annotators).
3. **Assigning images** in AnnoLoop (O3).
4. **Slide map**: thumbnails from AnnoLoop, the map in AnnOverview.

Later: several annotators per image (the blending in AnnoLoop), more visualisation.

## Out of scope

- Writing anything to the shared folder; assigning images (AnnoLoop).
- A database: the shared folder is the only source of truth.
- Live status, and any timing of annotators.

## Existing data

Everything on the drive so far is test data: kept for trying things, deleted when no longer needed. Folders in format
1 show as problems ("export it again").
