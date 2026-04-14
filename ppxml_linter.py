#!/usr/bin/env python3
"""
Pipeline Pilot PPXML Protocol Linter
=====================================
Checks PPXML files against the Pipeline Pilot Good Practice Guide.

Usage:
    python ppxml_linter.py <file.ppxml> [--format markdown|csv|json]

Output formats:
    markdown  - Human-readable report (default), suitable for ADO wiki/work items
    csv       - For import into ADO or spreadsheets
    json      - Machine-readable for automation
"""

import xml.etree.ElementTree as ET
import re
import sys
import json
import csv
import io
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class Severity(Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"

class Category(Enum):
    NAMING = "3.1 Naming Conventions"
    LAYOUT = "3.2 Layout, Commenting & Style"
    SCOPE = "3.3 Controlling Scope"
    ERROR_HANDLING = "3.4 Error Handling"
    PERFORMANCE = "3.5 Performance"
    PILOTSCRIPT = "3.6 PilotScript"
    INTEGRATIONS = "3.7 Integrations"
    DATABASE = "3.8 Database Access"
    VERSION_CONTROL = "3.9 Version Control"
    PROTOCOL_DEV = "4.2 Protocol Development"
    COMPONENT_DEV = "4.3 Component Development"
    APP_DEV = "4.4 Application Development"
    GUIDS = "4.4.1 Protocol GUIDs"
    PACKAGES = "4.5 Packages"

@dataclass
class Finding:
    rule_id: str
    severity: Severity
    category: Category
    title: str
    description: str
    component_id: Optional[str] = None
    component_name: Optional[str] = None
    component_display: Optional[str] = None
    evidence: Optional[str] = None

    def location_str(self):
        parts = []
        if self.component_id:
            parts.append(f"ID:{self.component_id}")
        if self.component_display:
            parts.append(f'"{self.component_display}"')
        elif self.component_name:
            parts.append(f'"{self.component_name}"')
        return " / ".join(parts) if parts else "Protocol level"


@dataclass
class ComponentInfo:
    local_id: str = ""
    name: str = ""
    display_name: str = ""
    component_path: str = ""
    derived_from: str = ""
    guid: str = ""
    disabled: int = 0
    point: str = ""
    icon: str = ""
    expressions: list = field(default_factory=list)
    declare_global: str = ""
    declare_local: str = ""
    web_exports: str = ""
    on_general_error: str = ""
    on_data_type_error: str = ""
    custom_error_text: str = ""
    component_attributes: list = field(default_factory=list)
    cache_id: str = ""
    cache_scope: str = ""
    source: str = ""
    run_to_completion: str = ""
    sub_protocol_modified: bool = False
    by_reference: bool = False
    help_text: list = field(default_factory=list)
    sticky_notes: list = field(default_factory=list)
    registrant: str = ""
    original_package: str = ""
    object_type: str = ""
    is_protocol: bool = False
    is_subprotocol: bool = False
    nesting_depth: int = 0
    auth_method: str = ""
    url: str = ""
    username: str = ""
    has_password: bool = False
    tempfiles: str = ""
    message_expr: str = ""
    log_filename: str = ""


# =============================================================================
# PPXML PARSER
# =============================================================================

NS = '{http://www.SciTegic.com/}'

class PPXMLParser:
    """Parses a PPXML file into structured component data and connection graph."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.tree = ET.parse(filepath)
        self.root = self.tree.getroot()
        self.components: dict[str, ComponentInfo] = {}
        self.connections: list[tuple[str, str, str]] = []  # (from_id, to_id, port_type)
        self.protocol_name = ""
        self.protocol_path = ""
        self.protocol_guid = ""
        self.protocol_globals = ""
        self.protocol_tempfiles = ""
        self._parse()

    def _parse(self):
        self._walk(self.root, depth=0)
        self._parse_connections(self.root)

    def _walk(self, element, depth=0):
        """Recursively walk the PPXML tree and extract components."""
        tag = element.tag

        # If this element is a sci:component, extract it
        if tag == f'{NS}component':
            parent = element
            # Try to determine the object type from the parent sci:data
            obj_type = ""
            info = self._extract_component_info(element, obj_type, depth)

            if info.local_id == '-1' and depth <= 1:
                self.protocol_name = info.name
                self.protocol_path = info.component_path
                self.protocol_guid = info.guid
                self.protocol_globals = info.declare_global
                self.protocol_tempfiles = info.tempfiles
                info.is_protocol = True
                self.components['protocol'] = info
            elif info.local_id and info.local_id != '-1':
                key = f"{depth}:{info.local_id}"
                info.nesting_depth = depth
                self.components[key] = info

        # If this is a sci:data element, extract the object type and pass to children
        if tag == f'{NS}data':
            obj_type = element.get('object', '')
            for comp_elem in element.findall(f'{NS}component'):
                info = self._extract_component_info(comp_elem, obj_type, depth)

                if info.local_id == '-1' and depth <= 1 and not self.protocol_name:
                    self.protocol_name = info.name
                    self.protocol_path = info.component_path
                    self.protocol_guid = info.guid
                    self.protocol_globals = info.declare_global
                    self.protocol_tempfiles = info.tempfiles
                    info.is_protocol = True
                    self.components['protocol'] = info
                elif info.local_id and info.local_id != '-1':
                    key = f"{depth}:{info.local_id}"
                    info.nesting_depth = depth
                    info.is_subprotocol = 'Protocol' in obj_type
                    info.object_type = obj_type
                    self.components[key] = info

            # Recurse into nested protocol elements within this data
            for proto_elem in element.findall(f'{NS}protocol'):
                self._walk(proto_elem, depth=depth + 1)

            # Recurse into nested data elements
            for data_elem in element.findall(f'{NS}data'):
                self._walk(data_elem, depth=depth + 1)

        # For modernitem, protocol, dbitem, and root data elements, recurse into children
        wrapper_tags = (f'{NS}modernitem', f'{NS}protocol', f'{NS}dbitem')
        if tag in wrapper_tags:
            next_depth = depth + 1 if tag == f'{NS}protocol' else depth
            for child in element:
                self._walk(child, depth=next_depth)
        elif tag == f'{NS}data':
            # Also recurse into modernitem and dbitem children of data elements
            for child in element:
                child_tag = child.tag
                if child_tag in wrapper_tags or child_tag == f'{NS}data':
                    self._walk(child, depth=depth)

    def _extract_component_info(self, comp_elem, obj_type, depth):
        """Extract all relevant fields from a component element."""
        info = ComponentInfo()
        info.name = comp_elem.get('name', '')
        info.object_type = obj_type
        info.nesting_depth = depth

        for arg in comp_elem.findall(f'{NS}arg'):
            arg_name = arg.get('name', '')
            val_elem = arg.find(f'{NS}value')
            val = val_elem.text if val_elem is not None and val_elem.text else ""
            vals = [v.text for v in arg.findall(f'{NS}value') if v.text is not None]

            # Selected legalval
            selected = None
            for lv in arg.findall(f'{NS}legalval'):
                if lv.get('selected') == 'true':
                    selected = lv.text or ""

            selected_all = []
            for lv in arg.findall(f'{NS}legalval'):
                if lv.get('selected') == 'true' and lv.text:
                    selected_all.append(lv.text)

            if arg_name == 'ComponentLocalID':
                info.local_id = val
            elif arg_name == 'ComponentDisplayName':
                info.display_name = val
            elif arg_name == 'Component Path':
                info.component_path = val
            elif arg_name == 'DerivedFrom':
                info.derived_from = val
            elif arg_name == 'ComponentGUID':
                info.guid = val
            elif arg_name == 'ComponentDisabled':
                info.disabled = int(val) if val else 0
            elif arg_name == 'ComponentPoint':
                info.point = val
            elif arg_name == 'ComponentIcon':
                info.icon = val
            elif arg_name == 'Expression':
                info.expressions.append(val)
            elif arg_name == 'Initial Expression' and val:
                info.expressions.append(val)
            elif arg_name == 'Final Expression' and val:
                info.expressions.append(val)
            elif arg_name == 'DeclareGlobal':
                info.declare_global = val
            elif arg_name == 'DeclareLocal':
                info.declare_local = val
            elif arg_name == 'WebExports':
                info.web_exports = val
            elif arg_name == 'OnGeneralError' and selected:
                info.on_general_error = selected
            elif arg_name == 'OnDataTypeError' and selected:
                info.on_data_type_error = selected
            elif arg_name == 'CustomErrorText':
                info.custom_error_text = val
            elif arg_name == 'ComponentAttributes':
                info.component_attributes = selected_all
            elif arg_name == 'CacheID':
                info.cache_id = val
            elif arg_name == 'Scope' and selected:
                info.cache_scope = selected
            elif arg_name == 'Source':
                info.source = val
            elif arg_name == 'RunToCompletion':
                info.run_to_completion = selected or val
            elif arg_name == 'SubProtocolModified':
                info.sub_protocol_modified = val == '1'
            elif arg_name == 'ByReference':
                info.by_reference = val == '1'
            elif arg_name == 'ComponentHelp':
                info.help_text = vals
            elif arg_name == 'Protocol Sticky Notes' or arg_name == 'Component Sticky Notes':
                info.sticky_notes.extend(vals)
            elif arg_name == 'Registrant':
                info.registrant = val
            elif arg_name == 'OriginalPackage':
                info.original_package = val
            elif arg_name == 'Authentication Method' and selected:
                info.auth_method = selected
            elif arg_name == 'Username':
                info.username = val
            elif arg_name == 'Password' and val:
                info.has_password = True
            elif arg_name == 'Tempfiles':
                info.tempfiles = val
            elif arg_name == 'Message':
                info.message_expr = val
            elif arg_name == 'Filename' and 'ApplicationLog' in obj_type:
                info.log_filename = val

        return info

    def _parse_connections(self, element):
        """Parse all connection elements from the protocol."""
        for conn in element.iter(f'{NS}connectid'):
            fr = conn.get('from', '')
            to = conn.get('to', '')
            tp = conn.get('type', '')
            self.connections.append((fr, to, tp))

    def get_active_components(self):
        """Return only enabled, non-protocol components."""
        return {k: v for k, v in self.components.items()
                if k != 'protocol' and v.local_id != '-1'}

    def get_connection_sources(self):
        """Get set of all component IDs that appear as 'from' in connections."""
        return {c[0] for c in self.connections}

    def get_connection_targets(self):
        """Get set of all component IDs that appear as 'to' in connections."""
        return {c[1] for c in self.connections}

    def get_pass_connections_from(self, comp_id):
        """Get connections from a component via pass (green) port."""
        return [(f, t, p) for f, t, p in self.connections if f == comp_id and p == 'true']

    def get_fail_connections_from(self, comp_id):
        """Get connections from a component via fail (red) port."""
        return [(f, t, p) for f, t, p in self.connections if f == comp_id and p == 'false']


# =============================================================================
# LINT RULES
# =============================================================================

SYSTEM_GLOBALS = {
    'RunId', 'username', 'ErrorText', 'ErrorDetails', 'JobDir',
    'ServerName', 'ServerPort', 'ServerRoot', 'TempDir',
    'ProtocolName', 'ProtocolPath', 'JobID', 'UserName',
    'HTTPRequest', 'HTTPResponse', 'HTTPMethod', 'HTTPPath',
    'ContentType', 'Https-Status-Code', 'REMOTE_ADDR',
}

def check_naming_globals(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.1: Global properties should be PascalCase."""
    findings = []
    pascal_re = re.compile(r'^[A-Z][a-zA-Z0-9_]*$')

    # gname -> list of ComponentInfo, deduplicated by local_id, first-seen order
    usage: dict[str, list] = {}
    for key, comp in parser.get_active_components().items():
        for expr in comp.expressions:
            # Match any @Global reference (read or write) — not just assignments
            for match in re.finditer(r'@(\w+)', expr):
                gname = match.group(1)
                if gname in SYSTEM_GLOBALS:
                    continue
                if pascal_re.match(gname):
                    continue
                if gname not in usage:
                    usage[gname] = []
                if all(c.local_id != comp.local_id for c in usage[gname]):
                    usage[gname].append(comp)

    for gname, comps in usage.items():
        first = comps[0]
        n = len(comps)
        ids = [c.local_id for c in comps[:10]]
        id_list = ", ".join(f"ID:{i}" for i in ids)
        if n > 10:
            id_list += f" +{n - 10} more"
        findings.append(Finding(
            rule_id="NAMING-001",
            severity=Severity.WARNING,
            category=Category.NAMING,
            title=f"Global property @{gname} is not PascalCase",
            description=(
                f"Global properties should be written in PascalCase (e.g. @GlobalProperty). "
                f"Found '@{gname}' ({n} component{'s' if n != 1 else ''}: {id_list})."
            ),
            component_id=first.local_id,
            component_name=first.name,
            component_display=first.display_name,
            evidence=f"@{gname} (used in {n} location{'s' if n != 1 else ''})",
        ))
    return findings


def check_naming_locals(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.1: Local properties should be camelCase."""
    findings = []
    camel_re = re.compile(r'^[a-z][a-zA-Z0-9_]*$')
    # Very short or single-char loop vars are OK
    skip_re = re.compile(r'^[a-z]$|^#?[ij]$')

    # lname -> list of ComponentInfo, deduplicated by local_id, first-seen order
    usage: dict[str, list] = {}
    for key, comp in parser.get_active_components().items():
        for expr in comp.expressions:
            for match in re.finditer(r'#(\w+)\s*:?=', expr):
                lname = match.group(1)
                if skip_re.match(lname):
                    continue
                if camel_re.match(lname):
                    continue
                if lname not in usage:
                    usage[lname] = []
                if all(c.local_id != comp.local_id for c in usage[lname]):
                    usage[lname].append(comp)

    for lname, comps in usage.items():
        first = comps[0]
        n = len(comps)
        ids = [c.local_id for c in comps[:10]]
        id_list = ", ".join(f"ID:{i}" for i in ids)
        if n > 10:
            id_list += f" +{n - 10} more"
        findings.append(Finding(
            rule_id="NAMING-002",
            severity=Severity.INFO,
            category=Category.NAMING,
            title=f"Local property #{lname} is not camelCase",
            description=(
                f"Local properties should be written in camelCase (e.g. #localProperty). "
                f"Found '#{lname}' ({n} component{'s' if n != 1 else ''}: {id_list})."
            ),
            component_id=first.local_id,
            component_name=first.name,
            component_display=first.display_name,
            evidence=f"#{lname} (used in {n} location{'s' if n != 1 else ''})",
        ))
    return findings


def check_naming_protocol(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.1: Protocol/component names should use capital+spaces convention."""
    findings = []
    # Check if name uses underscores instead of spaces
    name = parser.protocol_name
    if '_' in name:
        findings.append(Finding(
            rule_id="NAMING-003",
            severity=Severity.WARNING,
            category=Category.NAMING,
            title="Protocol name uses underscores instead of spaces",
            description=f'Protocol name "{name}" uses underscores. Convention is capitalized words with spaces (e.g. "Group Data by Tag").',
            evidence=name
        ))
    return findings


def check_disabled_components(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.2: Remove unused/redundant components."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            findings.append(Finding(
                rule_id="LAYOUT-001",
                severity=Severity.WARNING,
                category=Category.LAYOUT,
                title=f"Disabled component left in protocol",
                description=f'Component "{comp.display_name or comp.name}" is disabled (status={comp.disabled}). Remove disabled components unless kept for debug/troubleshooting purposes.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
                evidence=f"ComponentDisabled={comp.disabled}"
            ))
    return findings


def check_display_names(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.2: Built-in components should be renamed to indicate purpose."""
    findings = []
    # Components that should definitely be renamed
    generic_names = {
        'Custom Manipulator (PilotScript)', 'Custom Filter (PilotScript)',
        'Subprotocol', 'Custom Manipulator (Perl)',
        'Custom Manipulator (Java)', 'Custom Generator (PilotScript)',
    }

    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.name in generic_names and not comp.display_name:
            findings.append(Finding(
                rule_id="LAYOUT-002",
                severity=Severity.WARNING,
                category=Category.LAYOUT,
                title=f"Generic component not renamed",
                description=f'Component "{comp.name}" (ID:{comp.local_id}) has no custom display name. Rename components to indicate their purpose (e.g. "Calculate Batch Size" instead of "Custom Manipulator (PilotScript)").',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))
    return findings


def check_unused_ports(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.2: Remove unused ports."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        attrs = comp.component_attributes
        has_pass_port = 'ComponentReturnsPass' in attrs
        has_fail_port = 'ComponentReturnsFail' in attrs

        pass_conns = parser.get_pass_connections_from(comp.local_id)
        fail_conns = parser.get_fail_connections_from(comp.local_id)

        if has_pass_port and not pass_conns and has_fail_port:
            # Pass port declared but not connected (and fail exists, so this isn't a terminal)
            findings.append(Finding(
                rule_id="LAYOUT-003",
                severity=Severity.INFO,
                category=Category.LAYOUT,
                title=f"Pass port declared but not connected",
                description=f'Component "{comp.display_name or comp.name}" declares a Pass port but has no outgoing Pass connections.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))

        if has_fail_port and not fail_conns and has_pass_port:
            # Fail port declared but not connected
            findings.append(Finding(
                rule_id="LAYOUT-004",
                severity=Severity.INFO,
                category=Category.LAYOUT,
                title=f"Fail port declared but not connected",
                description=f'Component "{comp.display_name or comp.name}" declares a Fail port but has no outgoing Fail connections. Consider using "Don\'t Pass Data" or removing the port.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))
    return findings


def _assigns_globals(comp) -> bool:
    """Return True if any expression on this component contains a non-system global assignment.

    A global assignment is @Name := ... where Name is not in SYSTEM_GLOBALS.
    Components that assign globals are consuming data to populate shared state —
    a legitimate terminal behaviour — so LAYOUT-005 should not fire for them.
    """
    assign_re = re.compile(r'@(\w+)\s*:=')
    for expr in comp.expressions:
        for m in assign_re.finditer(expr):
            if m.group(1) not in SYSTEM_GLOBALS:
                return True
    return False


def check_dead_end_components(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.2: Check for components that receive data but don't pass it anywhere."""
    findings = []
    sources = parser.get_connection_sources()
    targets = parser.get_connection_targets()

    # Terminal components that legitimately don't output (writers, loggers, viewers)
    terminal_types = {'Cache Writer', 'Application Log', 'No-op', 'Data to Fail Port',
                      'File Writer', 'Text Writer', 'SD Writer', 'Delimited Text Writer',
                      'Excel Writer', 'XML Writer'}

    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        is_target = comp.local_id in targets
        is_source = comp.local_id in sources
        is_terminal = comp.name in terminal_types or comp.derived_from in terminal_types

        if is_target and not is_source and not is_terminal:
            # Suppress if the component assigns global properties — it is consuming
            # the data to populate shared state for later pipeline stages, which is
            # a legitimate terminal pattern even without outgoing connections.
            if _assigns_globals(comp):
                continue
            findings.append(Finding(
                rule_id="LAYOUT-005",
                severity=Severity.INFO,
                category=Category.LAYOUT,
                title=f"Dead-end component (receives data, outputs nothing)",
                description=f'Component "{comp.display_name or comp.name}" (ID:{comp.local_id}) receives data but has no outgoing connections and is not a known terminal component (writer/logger).',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))
    return findings


def check_orphaned_components(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.2: Check for components not connected to anything."""
    findings = []
    sources = parser.get_connection_sources()
    targets = parser.get_connection_targets()
    all_connected = sources | targets

    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.local_id not in all_connected and comp.nesting_depth <= 1:
            findings.append(Finding(
                rule_id="LAYOUT-006",
                severity=Severity.WARNING,
                category=Category.LAYOUT,
                title=f"Orphaned component (not connected to any pipeline)",
                description=f'Component "{comp.display_name or comp.name}" (ID:{comp.local_id}) is not connected to any other component.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))
    return findings


def check_undeclared_globals(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.3: Global variables should be declared with DeclareGlobal/DeclareLocal."""
    findings = []

    # Collect all declared globals
    declared = set()
    if parser.protocol_globals:
        for g in re.split(r'[,\s]+', parser.protocol_globals):
            g = g.strip().split(':=')[0].strip()
            if g:
                declared.add(g)

    # Collect DeclareLocal from all components
    for key, comp in parser.components.items():
        if comp.declare_local:
            for g in re.split(r'[,\s]+', comp.declare_local):
                g = g.strip().split(':=')[0].strip()
                if g:
                    declared.add(g)
        if comp.tempfiles:
            for g in re.split(r'[,\s]+', comp.tempfiles):
                g = g.strip()
                if g:
                    declared.add(g)
                    declared.add(g + '_Filename')

    # Scan expressions for any @Global reference (read or write)
    # gname -> list of ComponentInfo, in first-seen order, deduplicated by local_id
    usage: dict[str, list] = {}
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        for expr in comp.expressions:
            for match in re.finditer(r'@(\w+)', expr):
                gname = match.group(1)
                if gname in SYSTEM_GLOBALS or gname in declared:
                    continue
                if gname not in usage:
                    usage[gname] = []
                # Record each component once per global
                if all(c.local_id != comp.local_id for c in usage[gname]):
                    usage[gname].append(comp)

    for gname, comps in usage.items():
        first = comps[0]
        n = len(comps)

        # Build compact component ID list, capped at 10
        ids = [c.local_id for c in comps[:10]]
        id_list = ", ".join(f"ID:{i}" for i in ids)
        if n > 10:
            id_list += f" +{n - 10} more"

        findings.append(Finding(
            rule_id="SCOPE-001",
            severity=Severity.ERROR,
            category=Category.SCOPE,
            title=f"Undeclared global property @{gname}",
            description=(
                f"Global property @{gname} is used but not declared in DeclareGlobal or "
                f"DeclareLocal ({n} component{'s' if n != 1 else ''}: {id_list}). "
                f"Use DeclareLocal on the containing subprotocol to properly scope this variable."
            ),
            component_id=first.local_id,
            component_name=first.name,
            component_display=first.display_name,
            evidence=f"@{gname} (used in {n} location{'s' if n != 1 else ''})",
        ))
    return findings


def check_cache_scope(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.3: Cache scope should be 'Job Only' and use temporary CacheIDs."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.name == 'Cache Writer' or comp.derived_from == 'Cache Writer':
            # Check scope
            if comp.cache_scope and comp.cache_scope != 'Job Only':
                findings.append(Finding(
                    rule_id="SCOPE-002",
                    severity=Severity.WARNING,
                    category=Category.SCOPE,
                    title=f"Cache scope is not 'Job Only'",
                    description=f'Cache "{comp.cache_id}" has scope "{comp.cache_scope}". Set scope to "Job Only" to ensure cache data is deleted after each job.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=f"CacheID={comp.cache_id}, Scope={comp.cache_scope}"
                ))

            # Check for hardcoded cache IDs (not using $(TEMPVAR) pattern)
            if comp.cache_id and not re.search(r'\$\(', comp.cache_id):
                findings.append(Finding(
                    rule_id="SCOPE-003",
                    severity=Severity.INFO,
                    category=Category.SCOPE,
                    title=f"Hardcoded Cache ID",
                    description=f'Cache ID "{comp.cache_id}" is hardcoded. Consider using "Create Temporary CacheIDs" component to avoid cache conflicts.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=f"CacheID={comp.cache_id}"
                ))
    return findings


def check_subprotocol_declare_local(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.3 / 4.3: Subprotocols using globals should have DeclareLocal."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        is_subproto = (comp.name == 'Subprotocol' or comp.derived_from == 'SubProtocol'
                       or comp.is_subprotocol or 'Protocol' in comp.object_type)
        if not is_subproto:
            continue
        if comp.local_id == '-1':
            continue

        # Check if any expressions inside write globals
        has_global_writes = False
        for expr in comp.expressions:
            if re.search(r'@\w+\s*:=', expr):
                has_global_writes = True
                break

        if has_global_writes and not comp.declare_local:
            findings.append(Finding(
                rule_id="SCOPE-004",
                severity=Severity.WARNING,
                category=Category.SCOPE,
                title=f"Subprotocol writes globals without DeclareLocal",
                description=f'Subprotocol "{comp.display_name or comp.name}" assigns global properties but has no DeclareLocal parameter set. Scope global properties to the subprotocol using DeclareLocal.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))
    return findings


def check_error_handling(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.4 / 4.2.1: Components likely to error should have error handling."""
    findings = []
    risky_types = {'HTTP Connector', 'SQL Executor', 'SQL Query', 'Run Program',
                   'Run Program (on Server)', 'SOAP Connector', 'Oracle Query'}

    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        is_risky = comp.name in risky_types or comp.derived_from in risky_types
        if not is_risky:
            continue

        if comp.on_general_error == 'Halt':
            findings.append(Finding(
                rule_id="ERROR-001",
                severity=Severity.WARNING,
                category=Category.ERROR_HANDLING,
                title=f"Risky component halts on error instead of handling it",
                description=f'Component "{comp.display_name or comp.name}" is set to Halt on error. Consider placing it in a subprotocol with error handling to route errors to the Fail port with a custom error message.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
                evidence=f"OnGeneralError=Halt"
            ))
    return findings


def check_pilotscript_hierarchical(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.6: Use Property('/path') not %'/path' for hierarchical properties."""
    findings = []
    bad_pattern = re.compile(r"%'//|%'/[a-zA-Z]")

    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        for expr in comp.expressions:
            matches = bad_pattern.findall(expr)
            if matches:
                findings.append(Finding(
                    rule_id="PSCRIPT-001",
                    severity=Severity.WARNING,
                    category=Category.PILOTSCRIPT,
                    title=f"Hierarchical property accessed via %' instead of Property()",
                    description=f'PilotScript uses %\'/path\' syntax for hierarchical property access. Use Property(\'/path/to/property\') instead per good practice guide.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=matches[0] + "..."
                ))
    return findings


def check_pilotscript_defensive(parser: PPXMLParser) -> list[Finding]:
    """Rule 3.6: Code defensively - check properties are defined before use."""
    findings = []
    # Look for direct property access in conditionals without 'is defined'
    # This is a heuristic - may have false positives
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.derived_from != 'Custom Filter (PilotScript)':
            continue
        for expr in comp.expressions:
            # Check if filter uses a property without checking 'is defined'
            prop_accesses = re.findall(r'(?:^|\s)(\w+)\s*(?:=|<>|!=|<|>|<=|>=)\s', expr)
            has_defined_check = 'is defined' in expr or 'Is Defined' in expr
            if prop_accesses and not has_defined_check and 'defined' not in expr.lower():
                findings.append(Finding(
                    rule_id="PSCRIPT-002",
                    severity=Severity.INFO,
                    category=Category.PILOTSCRIPT,
                    title=f"Filter may not check if properties are defined",
                    description=f'Custom filter accesses properties without an "is defined" check. Code defensively by checking properties exist before comparing them.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=expr[:120] + "..." if len(expr) > 120 else expr
                ))
    return findings


def check_locally_modified(parser: PPXMLParser) -> list[Finding]:
    """Rule 4.2: Protocols should not contain locally modified components."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.sub_protocol_modified:
            findings.append(Finding(
                rule_id="PROTO-001",
                severity=Severity.WARNING,
                category=Category.PROTOCOL_DEV,
                title=f"Locally modified component found",
                description=f'Component "{comp.display_name or comp.name}" is a locally modified subprotocol. Changes should be saved back to the master component or a local copy should be made.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
            ))
    return findings


def check_dev_path(parser: PPXMLParser) -> list[Finding]:
    """Rule 4.4: Do not develop under personal/dev directories."""
    findings = []
    path = parser.protocol_path
    if not path:
        return findings

    dev_patterns = [r'\\DEV\\', r'\\Dev\\', r'\\dev\\', r'\\Personal\\',
                    r'\\personal\\', r'\\Test\\', r'\\Sandbox\\', r'\\sandbox\\']
    for pattern in dev_patterns:
        if re.search(pattern, path):
            findings.append(Finding(
                rule_id="APPDEV-001",
                severity=Severity.WARNING,
                category=Category.APP_DEV,
                title=f"Protocol stored in development/personal directory",
                description=f'Protocol is stored at "{path}". Do not perform development under a development or personal location as changes will need to be moved and may introduce integration issues.',
                evidence=path
            ))
            break
    return findings


def check_guid_exists(parser: PPXMLParser) -> list[Finding]:
    """Rule 4.4.1: Components and protocols should have GUIDs."""
    findings = []
    if not parser.protocol_guid:
        findings.append(Finding(
            rule_id="GUID-001",
            severity=Severity.ERROR,
            category=Category.GUIDS,
            title="Protocol has no GUID",
            description="Protocol does not have a ComponentGUID set. GUIDs are critical for Pipeline Pilot to reference components correctly.",
        ))
    return findings


def check_hardcoded_paths(parser: PPXMLParser) -> list[Finding]:
    """Heuristic: Flag hardcoded UNC paths and URLs in expressions and sources."""
    findings = []
    path_re = re.compile(r'\\\\[A-Za-z0-9]|[A-Za-z]:\\\\')
    url_re = re.compile(r'https?://[^\s\'"]+', re.IGNORECASE)

    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue

        # Check Source parameters
        if comp.source:
            if path_re.search(comp.source):
                findings.append(Finding(
                    rule_id="INTEG-001",
                    severity=Severity.INFO,
                    category=Category.INTEGRATIONS,
                    title=f"Hardcoded file path in Source parameter",
                    description=f'Component has a hardcoded file path. Consider using a global property or package variable for paths that may change between environments.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=comp.source[:150]
                ))

        # Check expressions for hardcoded paths
        for expr in comp.expressions:
            urls = url_re.findall(expr)
            for url in urls:
                findings.append(Finding(
                    rule_id="INTEG-002",
                    severity=Severity.INFO,
                    category=Category.INTEGRATIONS,
                    title=f"Hardcoded URL in expression",
                    description=f'Expression contains a hardcoded URL. Consider using a package variable or implementation parameter for URLs that differ between environments.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=url[:120]
                ))
    return findings


def check_incomplete_comments(parser: PPXMLParser) -> list[Finding]:
    """Heuristic: Flag TODO/incomplete logic in sticky notes and expressions."""
    findings = []
    todo_re = re.compile(r'(?:TODO|FIXME|HACK|XXX|need\s+(?:to|logic)|still\s+need|not\s+yet\s+(?:built|implemented|done))', re.IGNORECASE)

    for key, comp in parser.components.items():
        # Check sticky notes
        for note in comp.sticky_notes:
            if note and todo_re.search(note):
                findings.append(Finding(
                    rule_id="LAYOUT-007",
                    severity=Severity.INFO,
                    category=Category.LAYOUT,
                    title=f"Incomplete/TODO comment found",
                    description=f'A sticky note or comment contains language suggesting incomplete work.',
                    component_id=comp.local_id if comp.local_id != '-1' else None,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=todo_re.search(note).group()[:80]
                ))

        # Check expressions for TODO comments
        for expr in comp.expressions:
            for match in todo_re.finditer(expr):
                # Get surrounding context
                start = max(0, match.start() - 20)
                end = min(len(expr), match.end() + 60)
                context = expr[start:end].replace('\n', ' ').strip()
                findings.append(Finding(
                    rule_id="LAYOUT-008",
                    severity=Severity.INFO,
                    category=Category.LAYOUT,
                    title=f"TODO/incomplete logic in PilotScript",
                    description=f'Expression contains a comment suggesting incomplete work.',
                    component_id=comp.local_id if comp.local_id != '-1' else None,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=context
                ))
    return findings


def check_hardcoded_conditionals(parser: PPXMLParser) -> list[Finding]:
    """Heuristic: Flag long hardcoded if/elsif chains that should be config."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        for expr in comp.expressions:
            elsif_count = len(re.findall(r'\belsif\b', expr, re.IGNORECASE))
            if elsif_count >= 4:
                findings.append(Finding(
                    rule_id="PSCRIPT-003",
                    severity=Severity.INFO,
                    category=Category.PILOTSCRIPT,
                    title=f"Long if/elsif chain ({elsif_count} branches) - consider configuration table",
                    description=f'Expression contains {elsif_count} elsif branches. Consider replacing with a lookup table, cache join, or configuration file to improve maintainability.',
                    component_id=comp.local_id,
                    component_name=comp.name,
                    component_display=comp.display_name,
                    evidence=f"{elsif_count} elsif branches"
                ))
    return findings


def check_hardcoded_array_literals(parser: PPXMLParser) -> list[Finding]:
    """Heuristic: Flag hardcoded array literals used in filters."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if 'Filter' not in comp.name and 'Filter' not in comp.derived_from:
            continue
        for expr in comp.expressions:
            match = re.search(r"array\s*\(\s*'[^)]+'\s*\)", expr)
            if match:
                items = re.findall(r"'([^']*)'", match.group())
                if len(items) >= 5:
                    findings.append(Finding(
                        rule_id="PSCRIPT-004",
                        severity=Severity.INFO,
                        category=Category.PILOTSCRIPT,
                        title=f"Hardcoded array of {len(items)} values in filter",
                        description=f'Filter contains a hardcoded array of {len(items)} values. Consider moving these to a configuration file, cache, or global property for easier maintenance.',
                        component_id=comp.local_id,
                        component_name=comp.name,
                        component_display=comp.display_name,
                        evidence=match.group()[:120]
                    ))
    return findings


def check_credentials_in_xml(parser: PPXMLParser) -> list[Finding]:
    """Security: Flag embedded credentials."""
    findings = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.username and comp.has_password:
            findings.append(Finding(
                rule_id="SEC-001",
                severity=Severity.WARNING,
                category=Category.INTEGRATIONS,
                title=f"Embedded credentials in component",
                description=f'Component contains embedded username ("{comp.username}") and encrypted password. Consider using credential management or package variables for service account credentials.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
                evidence=f"Username={comp.username}"
            ))
    return findings


def check_duplicate_log_messages(parser: PPXMLParser) -> list[Finding]:
    """Heuristic: Flag Application Log components with identical messages."""
    findings = []
    log_components = []
    for key, comp in parser.get_active_components().items():
        if comp.disabled != 0:
            continue
        if comp.name == 'Application Log':
            log_components.append(comp)

    seen_messages = {}
    for comp in log_components:
        msg_key = (comp.message_expr, comp.log_filename)
        if msg_key in seen_messages:
            findings.append(Finding(
                rule_id="LAYOUT-009",
                severity=Severity.INFO,
                category=Category.LAYOUT,
                title=f"Duplicate Application Log message",
                description=f'Application Log "{comp.display_name or comp.name}" (ID:{comp.local_id}) has an identical message and filename to component ID:{seen_messages[msg_key]}. This may be a copy-paste issue.',
                component_id=comp.local_id,
                component_name=comp.name,
                component_display=comp.display_name,
                evidence=comp.message_expr[:100] if comp.message_expr else ""
            ))
        else:
            seen_messages[msg_key] = comp.local_id
    return findings


def check_protocol_help(parser: PPXMLParser) -> list[Finding]:
    """Rule 4.2: Protocols should have help text."""
    findings = []
    proto = parser.components.get('protocol')
    if proto:
        help_texts = [h for h in proto.help_text if h and h.strip() and h != '100'
                      and h != 'None' and h != parser.protocol_name]
        if not help_texts:
            findings.append(Finding(
                rule_id="PROTO-002",
                severity=Severity.WARNING,
                category=Category.PROTOCOL_DEV,
                title="Protocol has no meaningful help text",
                description='Protocol should have help text describing its purpose, expected inputs, and outputs.',
            ))
    return findings


# =============================================================================
# RUNNER & OUTPUT
# =============================================================================

ALL_CHECKS = [
    check_naming_globals,
    check_naming_locals,
    check_naming_protocol,
    check_disabled_components,
    check_display_names,
    check_unused_ports,
    check_dead_end_components,
    check_orphaned_components,
    check_undeclared_globals,
    check_cache_scope,
    check_subprotocol_declare_local,
    check_error_handling,
    check_pilotscript_hierarchical,
    check_pilotscript_defensive,
    check_locally_modified,
    check_dev_path,
    check_guid_exists,
    check_hardcoded_paths,
    check_incomplete_comments,
    check_hardcoded_conditionals,
    check_hardcoded_array_literals,
    check_credentials_in_xml,
    check_duplicate_log_messages,
    check_protocol_help,
]


def run_lint(filepath: str) -> tuple[PPXMLParser, list[Finding]]:
    """Run all lint checks against a PPXML file."""
    parser = PPXMLParser(filepath)
    findings = []
    for check_fn in ALL_CHECKS:
        try:
            findings.extend(check_fn(parser))
        except Exception as e:
            findings.append(Finding(
                rule_id="LINT-ERR",
                severity=Severity.ERROR,
                category=Category.LAYOUT,
                title=f"Linter error in {check_fn.__name__}",
                description=str(e),
            ))
    # Sort by severity then rule_id
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    findings.sort(key=lambda f: (severity_order[f.severity], f.rule_id))
    return parser, findings


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Remove exact duplicate findings."""
    seen = set()
    deduped = []
    for f in findings:
        key = (f.rule_id, f.component_id, f.evidence)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


def format_markdown(parser: PPXMLParser, findings: list[Finding]) -> str:
    """Format findings as a Markdown report suitable for ADO wiki."""
    lines = []
    lines.append(f"# PPXML Lint Report")
    lines.append(f"")
    lines.append(f"**Protocol:** {parser.protocol_name}")
    lines.append(f"**Path:** `{parser.protocol_path}`")
    lines.append(f"**GUID:** `{parser.protocol_guid}`")
    lines.append(f"**Scanned:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Components:** {len(parser.get_active_components())}")
    lines.append(f"**Connections:** {len(parser.connections)}")
    lines.append(f"")

    # Summary counts
    errors = [f for f in findings if f.severity == Severity.ERROR]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    infos = [f for f in findings if f.severity == Severity.INFO]

    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| :red_circle: Error | {len(errors)} |")
    lines.append(f"| :warning: Warning | {len(warnings)} |")
    lines.append(f"| :information_source: Info | {len(infos)} |")
    lines.append(f"| **Total** | **{len(findings)}** |")
    lines.append(f"")

    # Group by category
    by_category = {}
    for f in findings:
        cat = f.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f)

    for cat, cat_findings in by_category.items():
        lines.append(f"## {cat}")
        lines.append(f"")
        for f in cat_findings:
            sev_icon = {
                Severity.ERROR: ":red_circle:",
                Severity.WARNING: ":warning:",
                Severity.INFO: ":information_source:"
            }[f.severity]

            lines.append(f"### {sev_icon} [{f.rule_id}] {f.title}")
            lines.append(f"")
            lines.append(f"**Severity:** {f.severity.value}  ")
            lines.append(f"**Location:** {f.location_str()}  ")
            if f.evidence:
                lines.append(f"**Evidence:** `{f.evidence}`  ")
            lines.append(f"")
            lines.append(f"{f.description}")
            lines.append(f"")
            lines.append(f"---")
            lines.append(f"")

    return "\n".join(lines)


def format_csv(parser: PPXMLParser, findings: list[Finding]) -> str:
    """Format findings as CSV for ADO import."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rule ID", "Severity", "Category", "Title", "Description",
        "Component ID", "Component Name", "Component Display Name",
        "Evidence", "Protocol", "Protocol Path"
    ])
    for f in findings:
        writer.writerow([
            f.rule_id, f.severity.value, f.category.value, f.title,
            f.description, f.component_id or "", f.component_name or "",
            f.component_display or "", f.evidence or "",
            parser.protocol_name, parser.protocol_path
        ])
    return output.getvalue()


def format_json(parser: PPXMLParser, findings: list[Finding]) -> str:
    """Format findings as JSON."""
    data = {
        "protocol": parser.protocol_name,
        "protocol_path": parser.protocol_path,
        "protocol_guid": parser.protocol_guid,
        "scan_time": datetime.now().isoformat(),
        "component_count": len(parser.get_active_components()),
        "connection_count": len(parser.connections),
        "summary": {
            "errors": len([f for f in findings if f.severity == Severity.ERROR]),
            "warnings": len([f for f in findings if f.severity == Severity.WARNING]),
            "info": len([f for f in findings if f.severity == Severity.INFO]),
            "total": len(findings),
        },
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "category": f.category.value,
                "title": f.title,
                "description": f.description,
                "component_id": f.component_id,
                "component_name": f.component_name,
                "component_display": f.component_display,
                "evidence": f.evidence,
            }
            for f in findings
        ]
    }
    return json.dumps(data, indent=2)


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python ppxml_linter.py <file.ppxml> [--format markdown|csv|json]")
        sys.exit(1)

    filepath = sys.argv[1]
    fmt = "markdown"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]

    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    parser, findings = run_lint(filepath)
    findings = deduplicate_findings(findings)

    if fmt == "csv":
        print(format_csv(parser, findings))
    elif fmt == "json":
        print(format_json(parser, findings))
    else:
        print(format_markdown(parser, findings))


if __name__ == "__main__":
    main()
