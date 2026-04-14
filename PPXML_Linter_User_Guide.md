# PPXML Linter — User Guide

**Version:** 1.0  
**Date:** April 2026  
**Author:** Ewan Ross, 2026

---

## 1. What Is This?

The PPXML Linter is a static analysis tool for Pipeline Pilot protocol files. It reads the XML (`.ppxml`) export of a protocol and checks it against the rules defined in the Pipeline Pilot Good Practice Guide. Think of it as ESLint or pylint, but for Pipeline Pilot protocols.

It does **not** execute the protocol. It does **not** modify the protocol. It reads the XML, applies rules, and produces a report of findings.

### What It Checks

The linter currently implements 24 checks across 9 categories from the Good Practice Guide. Each check produces findings at one of three severity levels:

- **Error** — A definite violation that should be fixed before deployment.
- **Warning** — A likely violation or bad practice that should be reviewed.
- **Info** — A suggestion for improvement, or something that may be intentional but is worth noting.

### What It Does Not Check

Some rules in the Good Practice Guide cannot be verified from the XML alone:

- Version control practices (Git commits, branching)
- Whether automated tests exist
- GUI styling consistency
- Runtime performance characteristics
- Whether an API is the right integration approach vs. direct database access

These require human review or integration with other tools.

---

## 2. Requirements

- **Python 3.10 or later** (uses modern type hints)
- **No third-party packages** — the linter uses only the Python standard library (`xml.etree.ElementTree`, `re`, `json`, `csv`, `dataclasses`)
- Works on Windows, Linux, and macOS

Pipeline Pilot servers typically have Python installed. Run `python3 --version` to confirm.

---

## 3. How to Run

### Basic Usage

```
python3 ppxml_linter.py <path-to-file.ppxml>
```

This prints a Markdown-formatted report to the terminal (stdout).

### Output Formats

```
python3 ppxml_linter.py protocol.ppxml --format markdown
python3 ppxml_linter.py protocol.ppxml --format csv
python3 ppxml_linter.py protocol.ppxml --format json
```

### Saving to a File

```
python3 ppxml_linter.py protocol.ppxml --format markdown > lint_report.md
python3 ppxml_linter.py protocol.ppxml --format csv > lint_report.csv
```

### Exporting a Protocol for Linting

In Pipeline Pilot Client:

1. Right-click the protocol in the Component Explorer.
2. Select **Export to XML File...**
3. Save as `.ppxml`.
4. Run the linter against the exported file.

### Batch Linting (Multiple Files)

The linter processes one file at a time. To lint a directory of exports:

**Linux / macOS:**
```bash
for f in /path/to/exports/*.ppxml; do
    echo "=== $f ==="
    python3 ppxml_linter.py "$f" --format csv
done > all_findings.csv
```

**Windows (PowerShell):**
```powershell
Get-ChildItem *.ppxml | ForEach-Object {
    python3 ppxml_linter.py $_.FullName --format csv
} | Out-File all_findings.csv
```

Note: when combining CSV output from multiple files, the header row repeats for each file. Remove duplicates before importing.

---

## 4. Output Formats Explained

### Markdown (default)

Intended for pasting into ADO wiki pages, PR descriptions, or reading in any Markdown viewer. Structure:

- **Header** — protocol name, path, GUID, scan timestamp, component/connection counts.
- **Summary table** — count of errors, warnings, and info findings.
- **Findings grouped by Good Practice Guide section** — each finding shows its rule ID, severity, location within the protocol, evidence (the specific value or code that triggered it), and a description with remediation guidance.

### CSV

Intended for import into Azure DevOps as work items, or into Excel for tracking. Columns:

| Column | Description |
|--------|-------------|
| Rule ID | Unique identifier for the rule (e.g. `SCOPE-001`) |
| Severity | `Error`, `Warning`, or `Info` |
| Category | Good Practice Guide section (e.g. `3.3 Controlling Scope`) |
| Title | Short summary of the finding |
| Description | Detailed explanation including remediation advice |
| Component ID | Pipeline Pilot `ComponentLocalID` of the offending component |
| Component Name | Base component type name (e.g. `Custom Manipulator (PilotScript)`) |
| Component Display Name | Custom display name if one was set |
| Evidence | The specific value, code snippet, or pattern that triggered the finding |
| Protocol | Name of the protocol that was scanned |
| Protocol Path | Storage path of the protocol in the PLP XMLDB |

To import into ADO as work items, use the ADO CSV import feature or map the columns to your work item type fields.

### JSON

Intended for automation, pipeline integration, or feeding into other tools. Contains the same data as CSV but in a structured format with a top-level `summary` object and a `findings` array.

---

## 5. Rule Reference

### 3.1 Naming Conventions

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| NAMING-001 | Warning | Global properties (`@VarName`) should be PascalCase. Scans all PilotScript expressions for `@variable := ...` assignments and checks the casing. System globals like `@RunId` and `@username` are excluded. |
| NAMING-002 | Info | Local properties (`#varName`) should be camelCase. Scans expressions for `#variable := ...` patterns. Single-character loop variables (`#i`, `#j`) are excluded. |
| NAMING-003 | Warning | Protocol name should use capitalized words with spaces, not underscores. Checks the top-level protocol `name` attribute. |

**How to fix:** Rename the property in your PilotScript expressions. For protocol names, right-click the protocol and select Rename.

### 3.2 Layout, Commenting & Style

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| LAYOUT-001 | Warning | Disabled components left in the protocol. Checks `ComponentDisabled` value. A value of 0 means enabled; any other value means disabled. |
| LAYOUT-002 | Warning | Generic components (Custom Manipulator, Custom Filter, Subprotocol) that have not been given a descriptive display name. Checks whether `ComponentDisplayName` is empty for components whose base `name` is a known generic type. |
| LAYOUT-003 | Info | A component declares a Pass (green) port in its `ComponentAttributes` but no outgoing Pass connection exists in the connection graph. |
| LAYOUT-004 | Info | A component declares a Fail (red) port but no outgoing Fail connection exists. |
| LAYOUT-005 | Info | A component receives data (appears as a target in the connection graph) but has no outgoing connections and is not a known terminal type (Cache Writer, Application Log, File Writer, etc.). Data enters but never leaves. Components that assign global properties (`@Name :=`) in their expressions are exempt — they are treated as legitimate terminals that consume data to populate shared state for later pipeline stages. |
| LAYOUT-006 | Warning | A component is not connected to any other component at all — it appears in neither the `from` nor `to` side of any connection. |
| LAYOUT-007 | Info | Sticky notes contain language suggesting incomplete work (TODO, FIXME, "need to", "still need", "not yet implemented"). |
| LAYOUT-008 | Info | PilotScript expressions contain comments with incomplete-work language. Same patterns as LAYOUT-007 but inside code. |
| LAYOUT-009 | Info | Two Application Log components have identical message expressions and filenames. May indicate a copy-paste error where one should have been customised. |

**How to fix:**
- LAYOUT-001: Delete the disabled component, or add a sticky note explaining why it is retained for debugging.
- LAYOUT-002: Select the component, press F2 (or right-click > Rename), and give it a name describing what it does.
- LAYOUT-003/004: Use the component's Parameter panel to remove the unused port, or add a "Don't Pass Data" / "Data to Fail Port" component to make the routing explicit.
- LAYOUT-006: Connect it to the pipeline or delete it.

### 3.3 Controlling Scope

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| SCOPE-001 | Error | A global property is assigned (`@VarName := ...`) in a PilotScript expression but is not declared in any `DeclareGlobal` (protocol level) or `DeclareLocal` (subprotocol level) parameter. System-provided globals are excluded from this check. |
| SCOPE-002 | Warning | A Cache Writer component has its `Scope` set to something other than "Job Only". Shared or User-scoped caches persist beyond the job and can cause conflicts. |
| SCOPE-003 | Info | A Cache Writer uses a hardcoded `CacheID` string rather than a dynamic one from "Create Temporary CacheIDs" (indicated by `$(...)` token syntax). |
| SCOPE-004 | Warning | A subprotocol assigns global properties in its expressions but has no `DeclareLocal` parameter set, meaning the globals leak to the parent scope. |

**How to fix:**
- SCOPE-001: Add the global name to the `DeclareLocal` parameter of the containing subprotocol, or to `DeclareGlobal` at the protocol level if it genuinely needs protocol-wide scope.
- SCOPE-002: Change the cache `Scope` to "Job Only" unless you have a specific reason for persistence (and document that reason).
- SCOPE-003: Add a "Create Temporary CacheIDs" component and reference the generated ID via `$(TempCacheName)`.
- SCOPE-004: Open the subprotocol's parameters and add the global names to `DeclareLocal`.

### 3.4 Error Handling

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| ERROR-001 | Warning | A component that is likely to throw errors at runtime (HTTP Connector, SQL Executor, Run Program, SOAP Connector) has `OnGeneralError` set to "Halt". This means any error will stop the entire protocol with no opportunity for graceful handling. |

**How to fix:** Place the component inside a subprotocol and use the Error Handling tab to route errors to the Fail port. Add a custom error message either via the `CustomErrorText` parameter or a downstream Custom Manipulator.

### 3.6 PilotScript

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| PSCRIPT-001 | Warning | Hierarchical (XPath-style) properties accessed using `%'/path/to/property'` syntax instead of `Property('/path/to/property')`. The `Property()` function is the recommended approach per the Good Practice Guide. |
| PSCRIPT-002 | Info | A Custom Filter expression compares properties without first checking `is defined`. Only fires on Custom Filter components; may produce false positives if the defined check is elsewhere in the expression. |
| PSCRIPT-003 | Info | A PilotScript expression contains 4 or more `elsif` branches. Long conditional chains are hard to maintain and should usually be replaced with a lookup table, cache join, or configuration file. |
| PSCRIPT-004 | Info | A Custom Filter expression contains a hardcoded `array(...)` literal with 5 or more values. These value lists should be externalised to a configuration file or cache for maintainability. |

**How to fix:**
- PSCRIPT-001: Replace `%'/results/property'` with `Property('/results/property')`.
- PSCRIPT-002: Add `PropertyName is defined and` before the comparison.
- PSCRIPT-003/004: Move the lookup data to an Excel file, cache, or package variable, and use a Join or cache lookup instead.

### 3.7 Integrations

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| INTEG-001 | Info | A component's `Source` parameter contains a hardcoded file path (UNC or local). Paths that differ between environments should be package variables or global properties. |
| INTEG-002 | Info | A PilotScript expression contains a hardcoded URL. Same reasoning as INTEG-001. |
| SEC-001 | Warning | An HTTP Connector (or similar) component has an embedded username and encrypted password. While Pipeline Pilot encrypts the password in the XML, credentials stored in protocol files are exported with the protocol and may end up in version control. |

**How to fix:**
- INTEG-001/002: Replace the hardcoded value with a reference to a package variable (`$(PackageVarName)`) or a global property set via an implementation parameter.
- SEC-001: Use Pipeline Pilot's credential store or a package variable for the password, rather than embedding it in the component.

### 4.2 Protocol Development

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| PROTO-001 | Warning | A subprotocol has `SubProtocolModified` set to true, meaning it is a locally modified copy that has broken its link with the master component. Changes to the master will not propagate. |
| PROTO-002 | Warning | The top-level protocol has no meaningful help text. Help text should describe the protocol's purpose, expected inputs, and outputs. |

**How to fix:**
- PROTO-001: Save changes back to the master component, or make a deliberate local copy.
- PROTO-002: Right-click the protocol canvas, select Properties, and fill in the Help tab.

### 4.4 Application Development

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| APPDEV-001 | Warning | The protocol's storage path contains `\DEV\`, `\Personal\`, `\Sandbox\`, or similar development directory names. Protocols should be developed in their final location to avoid integration issues when moving. |

**How to fix:** Move the protocol to its intended production path (e.g. `Protocols\<Application Name>\`).

### 4.4.1 Protocol GUIDs

| Rule ID | Severity | What It Checks |
|---------|----------|----------------|
| GUID-001 | Error | The top-level protocol has no `ComponentGUID`. GUIDs are how Pipeline Pilot references components and protocols. A missing GUID will break shortcut references and package deployment. |

**How to fix:** This typically means the export was corrupted or the protocol was never properly saved. Re-save the protocol in Pipeline Pilot Client and re-export.

---

## 6. Understanding the Report

### Reading a Finding

Each finding in the Markdown report looks like this:

```
### ⚠️ [LAYOUT-002] Generic component not renamed

Severity: Warning
Location: ID:38 / "Custom Manipulator (PilotScript)"
Evidence: (none)

Component "Custom Manipulator (PilotScript)" (ID:38) has no custom display name.
Rename components to indicate their purpose.
```

- **Rule ID** (`LAYOUT-002`) — uniquely identifies the check. Use this when discussing findings or configuring rule exceptions.
- **Location** — the `ComponentLocalID` and display name (or base name) of the component. You can find this component in the Pipeline Pilot Client by looking at the Information tab, or by searching for it on the canvas. IDs are stable for a given version of the protocol.
- **Evidence** — the specific value, code snippet, or pattern that triggered the finding. For expression-based checks, this shows the relevant portion of the PilotScript code.

### Severity Guidance

Not every finding requires action. Use this guidance:

**Errors** should always be fixed. They represent definite violations that will cause problems (undeclared globals that may collide, missing GUIDs that break references).

**Warnings** should be reviewed and either fixed or explicitly accepted with justification. For example, a protocol in a `\DEV\` path is fine during active development but should be moved before deployment.

**Info** findings are suggestions. Some may be intentional design choices (a hardcoded cache ID that is genuinely unique, a long if/elsif chain that maps to a business requirement). Review them, and if the current approach is deliberate, no action is needed.

### False Positives

The linter uses static analysis and heuristics. It can produce false positives in these situations:

- **SCOPE-001 (undeclared globals):** System globals that the linter does not know about will be flagged. The linter maintains an allowlist of common system globals (`@RunId`, `@username`, `@ErrorText`, etc.) but your environment may have additional ones.
- **PSCRIPT-002 (defensive coding):** The `is defined` check may be in a preceding component or handled by a filter earlier in the pipeline, but the linter only looks within the same expression.
- **LAYOUT-005 (dead-end components):** Components that consume incoming data to assign global properties (`@Name :=`) are intentionally *not* flagged, even if they have no outgoing connections. This is a recognised terminal pattern — the component's output is the populated globals rather than a data stream. Only components with no outgoing connections *and* no global assignments are flagged.
- **SCOPE-003 (hardcoded cache IDs):** A hardcoded ID is fine if the cache is scoped to "Job Only" and the ID is unique within the job. The linter flags it as a suggestion, not an error.

When reviewing findings, use the evidence and component location to verify whether the finding is genuine before acting on it.

---

## 7. Integrating with Azure DevOps

### As a PR Gate

If your team exports protocols to Git (per Good Practice Guide section 3.9), you can add the linter to a build pipeline:

```yaml
# azure-pipelines.yml (example)
trigger:
  paths:
    include:
      - 'protocols/*.ppxml'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.10'

  - script: |
      ERRORS=0
      for f in protocols/*.ppxml; do
        python3 ppxml_linter.py "$f" --format json > /tmp/lint.json
        ERRS=$(python3 -c "import json; d=json.load(open('/tmp/lint.json')); print(d['summary']['errors'])")
        if [ "$ERRS" -gt 0 ]; then
          echo "##vso[task.logissue type=error]$f has $ERRS error(s)"
          ERRORS=1
        fi
      done
      exit $ERRORS
    displayName: 'Lint PPXML protocols'
```

This fails the build if any protocol has Error-level findings. Warnings and Info findings are reported but do not block.

### Creating Work Items from CSV

1. Run the linter with `--format csv`.
2. In ADO, go to Boards > Queries > Import Work Items.
3. Map the CSV columns to your work item fields (Title, Description, Tags for severity, etc.).

Alternatively, use the ADO REST API to automate work item creation from the JSON output.

---

## 8. Limitations

- **Single-file analysis only.** The linter does not resolve by-reference subprotocol links to other PPXML files. It analyses what is present in the exported file.
- **No runtime analysis.** The linter cannot detect issues that only manifest at execution time (performance bottlenecks, data type mismatches, connection timeouts).
- **Expression parsing is regex-based.** The linter does not have a full PilotScript parser. Complex expressions with nested strings, multi-line comments, or unusual formatting may not be correctly analysed.
- **Nested subprotocol depth.** Components inside deeply nested subprotocols (3+ levels) may not have unique IDs in the connection graph, which can cause some connection-based checks (unused ports, orphaned components) to miss findings or produce false positives at those depths.
- **System globals allowlist.** The linter's list of known system globals is not exhaustive. If your environment provides additional system globals, they will be flagged as undeclared. A future configuration file will allow extending this list.

---

## 9. Quick Reference Card

```
USAGE
    python3 ppxml_linter.py <file.ppxml> [--format markdown|csv|json]

EXAMPLES
    python3 ppxml_linter.py MyProtocol.ppxml                    # Markdown to terminal
    python3 ppxml_linter.py MyProtocol.ppxml > report.md        # Save markdown report
    python3 ppxml_linter.py MyProtocol.ppxml --format csv       # CSV for ADO import
    python3 ppxml_linter.py MyProtocol.ppxml --format json      # JSON for automation

EXIT CODES
    0   Success (findings may still exist)
    1   File not found or usage error

SEVERITY LEVELS
    Error     Fix before deployment
    Warning   Review and fix or accept with justification
    Info      Suggestion — may be intentional

RULE ID PREFIXES
    NAMING-   Naming conventions (section 3.1)
    LAYOUT-   Layout, commenting, style (section 3.2)
    SCOPE-    Controlling scope (section 3.3)
    ERROR-    Error handling (section 3.4)
    PSCRIPT-  PilotScript practices (section 3.6)
    INTEG-    Integrations (section 3.7)
    SEC-      Security (not in guide, added for safety)
    PROTO-    Protocol development (section 4.2)
    APPDEV-   Application development (section 4.4)
    GUID-     Protocol GUIDs (section 4.4.1)
```
