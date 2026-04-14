# PPXML Linter GUI

Desktop GUI wrapper around `ppxml_linter.py`.

## Requirements

### Core linter (`ppxml_linter.py`)
- Python 3.8+, stdlib only — no pip installs required.
  The linter runs on locked-down Pipeline Pilot servers where pip is unavailable.

### GUI (`ppxml_linter_app/`)
- Python 3.8+
- Tkinter (bundled with standard Python on Windows)

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

1. Click **Browse for file…** and select a `.ppxml` file.
2. The protocol name, path, and component/connection counts appear in the info bar.
3. Findings are listed below, grouped by severity (Errors → Warnings → Info).
   - Click a section header to collapse/expand it.
   - Observations (Info) are collapsed by default.

## Project layout

```
ppxml_linter_app/
  app.py              Main window and entry point
  ui/
    results_view.py   Scrollable, collapsible findings display
  README.md           This file

ppxml_linter.py       Core linter (parent directory — stdlib only, not modified)
```
