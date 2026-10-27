# AnnOverview: an overview of the annotation rounds

Status: design agreed, nothing built. Points marked *to decide* are still open.

## Goal

See at a glance where the annotation of the project stands: which ROIs each annotator has, which are done, what
each annotator is working on now, and what they worked on before. For Massimo only; nobody else runs it.

AnnOverview **only reads**. It never writes to the shared folder, so it can be left open and refreshed at any time
without risk to an annotation.

## Three repositories, three roles

| Repository | Role | Writes |
|---|---|---|
| [macroseg](../../macroseg) | the pipeline: proposes the ROIs, cuts them from the stores, segments them with the model of the round, writes each ROI folder for its annotator, closes a round, trains on the corrections | the ROI folders (`image.tif`, `start_masks.tif`, `annotation.json`) |
| [AnnoCell](../../AnnoCell) (public) | the annotation tool: the annotator opens an ROI folder, corrects it, the tool saves into the same folder; it does not know about macroseg | `masks.tif`, `cells.csv`, the review in `annotation.json`, the session log |
| AnnOverview (private) | the overview: reads the whole tree | nothing |

There is no live connection between them: they share files on the network drive. The contract is AnnoCell's folder
format (`annocell.folder`): macroseg writes it, AnnoCell reads and updates it, AnnOverview reads it. AnnOverview
depends on `annocell` core (numpy and tifffile only, no napari) and reads through it, so the field names and the
layout are defined in one place: if AnnoCell changes its format, AnnOverview picks it up or fails on
`format_version`, never shows wrong counts silently. It does not depend on macroseg.

Splitting slides into ROIs stays in macroseg: it needs the stores, the model and the rule that keeps training ROIs
away from the test region; done in code, a split is recorded and can be rerun.

## The shared folder

On fs4: `smb://fs4.irc.ugent.be/experimental/exp/units/u_csc/private/massimoz/<annotation root>`, mounted on the
annotators' laptops (Windows, through the VPN from home) and on Massimo's Mac, where AnnOverview reads it.

### Layout

```
<root>/
  alice/                      one folder per annotator: the only one the annotator opens
    round_03/<roi>/           an ROI folder in the AnnoCell layout
    round_02/<roi>/           an earlier round: closed, read-only in AnnoCell
  bob/
    round_03/<roi>/
  carla/
    test/<roi>/               the test region: drawn from scratch by one expert annotator
```

Annotator first, then round: each annotator has exactly one folder, their entry point. Opening their own folder
opens the latest round that is not closed. Rejected: `round_NN/<annotator>/<roi>/`, which groups by round but gives
each annotator one folder per round to choose from, and so a chance to open the wrong one.

- **Annotator names**: short, lowercase, letters, digits and `-` (e.g. `alice`), the same as folder name and in
  `annotation.json`; macroseg checks every name against one list, so a typo is an error, not a new annotator.
- **One annotator per ROI** for now: training takes one mask per ROI, and blending several annotators
  (macroseg `docs/concurrent_annotations.md`) is not built.
- Annotators work directly on the network drive, each only in their own folder (by trust, not permissions).

### Opening the wrong round

An annotator could open an earlier round by mistake and change annotations that were already used for training. So:

- when a round is over, macroseg **closes** it: it writes `closed_on` (a date) into the `annotation.json` of every
  ROI of that round;
- AnnoCell opens a closed ROI **read-only**: the annotator can look but not edit, and the panel says "round 2:
  closed";
- `annocell <annotator folder>` (or Open folder on it) opens the latest round that is not closed;
- folders are never moved when a round closes (moving files on a network drive while someone has them open is
  asking for trouble), and AnnOverview keeps the whole history.

### Fields AnnOverview reads

From `annotation.json` of each ROI. Those not in the AnnoCell format today become documented, optional fields of
`annocell.folder` (optional, so `format_version` stays 1):

| Field | Written by | Use |
|---|---|---|
| `annotator`, `round` | macroseg at export | the tree (also given by the folders; the record is the reference) |
| `image`, `source` (slide), `region` (`[y0, y1, x0, x1]` in slide pixels) | macroseg at export | which slide and where; the slide map |
| `mode` (`train` / `test`), `exported_on` | macroseg at export | test region apart; when assigned |
| `closed_on` | macroseg when a round ends | closed rounds read-only |
| `review` (cells, OK, unreviewed, `saved_at`) | AnnoCell at every save | status and last activity |

A tree walker in `annocell.folder` lists the ROI folders under the root with annotator and round, for macroseg and
AnnOverview alike.

### Sessions (history)

AnnoCell appends one line per session to `sessions.jsonl` in the ROI folder: when the ROI was opened and left, and
the active time (time with edits, pauses longer than a few minutes not counted). Sessions, not clicks. The
annotators are told that this is recorded and why (to measure correction effort per round).

## What AnnOverview shows

A local web page (NiceGUI), started with `annoverview <root>` on the Mac, read again with a **refresh button** (no
automatic polling).

- **Tree**: annotator → round → ROI, and the same by round → annotator, filterable by slide.
- **Status of an ROI**: not started (no `masks.tif` yet), in progress (*x* of *n* cells checked), complete (no cell
  unreviewed: done), closed (round over).
- **Per round**: ROIs assigned, complete (going into training, see Rounds) and unfinished, and their cells.
- **Now**: per annotator, the ROI saved last and when. Only as fresh as the last save: an annotator who stopped
  looks the same as one who is offline.
- **History** (with the sessions): per annotator, the ROIs worked on, when, for how long.
- **Slide map** (later): each slide with the ROIs and the test region drawn on it, coloured by status, over a
  thumbnail that macroseg writes once per slide (`slides/<slide>.png`).

## Rounds

One round = one model iteration: every ROI of round *N* starts from the segmentation of the model trained after
round *N − 1*. **Massimo decides when a round is over**; macroseg then closes it and trains. Not every ROI has to be
finished: training takes the complete ones only, an unfinished ROI is left out (and stays visible in AnnOverview).
So one slow or stuck ROI never holds back the next model.

**Training and scoring (macroseg, decided)**:

- **No validation split, from the first round**: every tile of every complete ROI goes into training. (macroseg
  today keeps about 20 % of the tiles aside as "test" tiles for a loss that no decision uses: it costs a fifth of
  the corrected cells.) ROIs are still cut into 256 x 256 tiles: Cellpose-SAM sees one random 256 x 256 crop per
  image and epoch, so tiles show every part of an ROI once per epoch.
- **Fixed training settings** (epochs, learning rate, ...): Cellpose's usual fine-tuning settings, kept the same
  every round, never changed after looking at a test score (the score would stop being independent).
- **Scored on the test regions only**: one test region per tissue, drawn from scratch by the expert annotator
  (see Test region).

**Going into training** = complete (at least one cell, none unreviewed). Decided by one function of
`annocell.folder` (`is_complete`), which macroseg's training and AnnOverview both call, so the count AnnOverview
shows per round is the number of ROIs the next training will take. (Training then cuts them into tiles and keeps
some aside for validation: AnnOverview counts ROIs and cells, not tiles.)

**ROIs per annotator per round**: *to decide*. Measured from the first real round (time per ROI from the sessions).
Fewer, smaller rounds iterate faster (the model improves sooner and the next corrections are quicker); the limit is
the time to train and export a round.

## Proposing ROIs (macroseg)

Rules for macroseg's ROI proposal, to build there:

- **Macrophages**: a minimum F4/80 signal, e.g. at least *N* cells above the F4/80 threshold of the baseline
  segmentation (starting from macroseg's `marker_windows`).
- **Tissue, not background**: at most a small fraction of the ROI beyond the edge of the tissue; needs a tissue
  mask per slide (a threshold on DAPI or autofluorescence).
- **Spread over the images**: each annotator gets ROIs from several images (more images and tissues are coming), not
  one image per annotator, so an annotator's style and an image's look are not confounded.
- **Away from the test region**: no ROI within one cell diameter of it (already enforced by macroseg).

## Test region

One test region **per tissue**, drawn from scratch by one expert annotator, never given to anyone else and never
used for training: a test region only measures the tissue it was drawn on. A new tissue gets one; a new slide of a
tissue already there only if its staining or quality looks clearly different. Size: about 100 macrophages, in a few
512 x 512 patches (AnnoCell's `docs/annotation_tool.md`). The folders are in that annotator's folder
(`<annotator>/test/<roi>/`).

## Sprints

1. **The format and the layout**, in the order of who depends on whom (macroseg and AnnOverview both build on
   `annocell.folder`):
   1. AnnoCell format (`folder.py` only, nothing changes for the annotators): the layout helpers, the optional
      fields, closing an ROI, the tree walker, `is_complete`.
   2. macroseg: export with `annotator` into the new layout; closing a round; readers and training on the new
      layout, one annotator per ROI; training without the validation split, with fixed settings.
   3. AnnoCell tool: the annotator and the round in the panel; closed ROIs read-only; opening an annotator folder
      opens the latest open round; saving that survives the network drive dropping (keep the masks in memory, one
      warning, retry). Needs only step 1: before or after step 2.
   4. AnnOverview: the repository; the tree with status and last save; refresh button; tried on folders exported
      by step 2.
2. **History**: sessions in AnnoCell; history and "now" in AnnOverview.
3. **Proposing ROIs** in macroseg, with the rules above.
4. **Slide map**: thumbnails from macroseg, the map in AnnOverview.

Later: several annotators per ROI (the blending in macroseg), more visualisation.

## Out of scope

- Writing anything to the shared folder; assigning or splitting ROIs (macroseg).
- A database: the shared folder is the only source of truth.
- Live status: AnnOverview shows what was saved, read when Massimo refreshes.

## Existing data

Everything on the drive so far is test data: kept for trying things, deleted when no longer needed.
