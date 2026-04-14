# PPXML Linter GUI

Desktop GUI wrapper around `ppxml_linter.py`.

## Requirements

### Core linter (`ppxml_linter.py`)
- Python 3.8+, stdlib only — no pip installs.
  The linter runs on locked-down Pipeline Pilot servers where pip is unavailable.

### GUI (`ppxml_linter_app/`)
- Python 3.8+
- Tkinter (bundled with standard Python on Windows)
- **tkinterdnd2** — for drag-and-drop support:

  ```
  pip install tkinterdnd2
  ```

  If `tkinterdnd2` is not installed the app still launches and the Browse
  button works normally. The drop zone shows a notice instead of a drop target.

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

1. **Drop** a `.ppxml` file onto the drop zone, or click **Browse…** in the toolbar.
2. The protocol name, path, and component/connection counts appear in the info bar.
3. Findings are listed below, grouped by severity (Errors → Warnings → Info).
   - Click a section header to collapse/expand it.
   - Observations (Info) are collapsed by default.

## Project layout

```
ppxml_linter_app/
  app.py              Main window and entry point
  ui/
    drop_zone.py      Drag-and-drop target widget (requires tkinterdnd2)
    results_view.py   Scrollable, collapsible findings display
  README.md           This file

ppxml_linter.py       Core linter (parent directory — stdlib only, not modified)
```
