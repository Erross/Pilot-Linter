# PPXML Linter GUI

Desktop GUI wrapper around `ppxml_linter.py`.

## Requirements

- Python 3.8+ (stdlib only — no pip installs required)
- Tkinter (included with standard Python on Windows)

## Running

From the `ppxml_linter_app/` directory:

```
python app.py
```

Or from the repo root:

```
python ppxml_linter_app/app.py
```

## Usage

1. Click **Browse…** in the toolbar and select a `.ppxml` file, or drag a file onto the drop zone (drag-and-drop coming in a future iteration).
2. The protocol name, path, and component/connection counts appear in the info bar.
3. Findings are listed below, grouped by severity (Errors → Warnings → Info).

## Project layout

```
ppxml_linter_app/
  app.py              Main window and entry point
  ui/
    drop_zone.py      Drop zone widget (phase 1: visual placeholder)
    results_view.py   Scrollable findings display
  README.md           This file

ppxml_linter.py       Core linter (parent directory, not modified)
```
