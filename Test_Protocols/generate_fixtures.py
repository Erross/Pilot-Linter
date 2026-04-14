"""
PPXML Linter Test Fixture Generator
====================================
Generates a minimal PPXML file for each lint rule, deliberately breaking
that rule so it can be used as a regression test fixture.

Design principles:
- Each fixture breaks exactly ONE rule where possible.
- A "clean baseline" is used for everything that isn't the target rule.
- Some cross-triggering is unavoidable (e.g. a fixture that tests
  "generic component not renamed" will necessarily contain an
  unnamed component, which is fine because that IS what the fixture tests).
- Where cross-triggering would be confusing, it's documented in the
  fixture's metadata.

Each fixture function returns (filename, xml_content, expected_rule_id).
"""

import os

# ---------------------------------------------------------------------------
# LOW-LEVEL BUILDERS
# ---------------------------------------------------------------------------

def _escape(text):
    """Escape XML special chars."""
    if text is None:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _arg(name, value, type_="StringType", multi=False):
    """Build a single sci:arg element."""
    if multi:
        if isinstance(value, (list, tuple)):
            values = "".join(f"<sci:value>{_escape(v)}</sci:value>" for v in value)
        else:
            values = f"<sci:value>{_escape(value)}</sci:value>"
        return f'<sci:arg name="{name}" type="{type_}" multi="true">{values}</sci:arg>'
    return f'<sci:arg name="{name}" type="{type_}"><sci:value>{_escape(value)}</sci:value></sci:arg>'


def _legalval_arg(name, selected_values, all_values=None, type_="StringType"):
    """Build an sci:arg with legalvals, marking some as selected."""
    if all_values is None:
        all_values = selected_values
    lvs = []
    for v in all_values:
        if v in selected_values:
            lvs.append(f'<sci:legalval selected="true">{_escape(v)}</sci:legalval>')
        else:
            lvs.append(f'<sci:legalval>{_escape(v)}</sci:legalval>')
    return f'<sci:arg name="{name}" type="{type_}" multi="true">{"".join(lvs)}</sci:arg>'


def _component(
    object_type="SciTegic.EvaluateExpression.1",
    component_name="Custom Manipulator (PilotScript)",
    local_id=1,
    display_name="Set Variable",
    derived_from="Custom Manipulator (PilotScript)",
    disabled=0,
    expression=None,
    initial_expression=None,
    final_expression=None,
    attributes=("ComponentTakesInput", "ComponentReturnsPass"),
    extra_args=(),
):
    """Build a <sci:data><sci:component> block."""
    args = []
    args.append(_arg("ComponentLocalID", local_id, "LongType"))
    args.append(_arg("ComponentDisplayName", display_name))
    args.append(_arg("DerivedFrom", derived_from))
    args.append(_arg("ComponentDisabled", disabled, "LongType"))

    # Attributes as legalvals
    all_attrs = ("ComponentTakesInput", "ComponentReturnsPass",
                 "ComponentReturnsFail", "ComponentRunsLocal")
    args.append(_legalval_arg("ComponentAttributes", set(attributes), all_attrs))

    if expression is not None:
        args.append(_arg("Expression", expression, "ExpressionType"))
    if initial_expression is not None:
        args.append(_arg("Initial Expression", initial_expression, "ExpressionType"))
    if final_expression is not None:
        args.append(_arg("Final Expression", final_expression, "ExpressionType"))

    for ea in extra_args:
        args.append(ea)

    args_str = "\n".join(f"        {a}" for a in args)
    return (f'<sci:data object="{object_type}">\n'
            f'    <sci:component name="{component_name}" version="2">\n'
            f'{args_str}\n'
            f'    </sci:component>\n'
            f'</sci:data>')


def _connection(from_id, to_id, port="true"):
    return f'<sci:connectid from="{from_id}" to="{to_id}" type="{port}"/>'


def _protocol(
    name="TestFixture",
    guid="{11111111-2222-3333-4444-555555555555}",
    path="Protocols\\Testing\\Fixtures",
    help_text="Test fixture for deliberate rule violation.",
    declare_global="",
    tempfiles="",
    sticky_note="",
    components=(),
    connections=(),
    extra_protocol_args=(),
):
    """Build a complete PPXML protocol document."""
    proto_args = []
    proto_args.append(_arg("ComponentLocalID", -1, "LongType"))
    if guid:
        proto_args.append(_arg("ComponentGUID", guid))
    proto_args.append(_arg("Component Path", path))
    proto_args.append(_arg("ComponentDisplayName", name))
    proto_args.append(_arg("ComponentDisabled", 0, "LongType"))

    # Help text: the linter filters out '100', 'None', blank, and the
    # protocol name itself. So for a "clean" help, we need something
    # meaningful. For PROTO-002 (no help), we pass empty string.
    if help_text:
        proto_args.append(_arg("ComponentHelp", ["100", help_text], multi=True))
    else:
        proto_args.append(_arg("ComponentHelp", ["100", "None"], multi=True))

    if declare_global:
        proto_args.append(_arg("DeclareGlobal", declare_global))
    if tempfiles:
        proto_args.append(_arg("Tempfiles", tempfiles))
    if sticky_note:
        # Sticky notes in real protocols have a specific format:
        # version marker, coords, color, then the text itself.
        proto_args.append(_arg("Protocol Sticky Notes",
                               ["%VERSION 3%", "0 0 400 200", "255 255 0", sticky_note],
                               multi=True))

    for ea in extra_protocol_args:
        proto_args.append(ea)

    proto_args_str = "\n".join(f"            {a}" for a in proto_args)
    comps_str = "\n".join(
        "\n".join(f"            {line}" for line in c.split("\n"))
        for c in components
    )
    conns_str = "\n".join(f"            {c}" for c in connections)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sci:data xmlns:sci="http://www.SciTegic.com/" object="SciTegic.Protocol.1" format="8.0.0">\n'
        '    <sci:modernitem>\n'
        f'        <sci:component name="{name}" version="2">\n'
        f'{proto_args_str}\n'
        '        </sci:component>\n'
        '        <sci:protocol>\n'
        f'{comps_str}\n'
        f'{conns_str}\n'
        '        </sci:protocol>\n'
        '    </sci:modernitem>\n'
        '</sci:data>\n'
    )


def _no_op_sink(local_id):
    """
    A No-op terminal component. The linter recognises 'No-op' as a terminal
    type and will not fire LAYOUT-005 (dead-end) against it. Use at the end
    of every fixture chain to avoid collateral findings.
    """
    return _component(
        object_type="SciTegic.EvaluateExpression.1",
        component_name="No-op",
        local_id=local_id,
        display_name="Sink",
        derived_from="Evaluate Expression",
        attributes=("ComponentTakesInput",),
        expression=None,
    )


# ---------------------------------------------------------------------------
# BASELINE — two connected components that pass every rule
# ---------------------------------------------------------------------------

def _clean_two_component_chain():
    """
    A baseline pair of two components: one Custom Manipulator feeding into
    a No-op terminal. This is the "boring filler" for fixtures that need
    components but don't care what they do.
    """
    c1 = _component(local_id=1, display_name="First Step",
                    expression="x := 1;")
    c2 = _no_op_sink(local_id=2)
    return [c1, c2], [_connection(1, 2)]


# ---------------------------------------------------------------------------
# FIXTURES — one per rule
# ---------------------------------------------------------------------------

FIXTURES = []

def fixture(rule_id, filename, description):
    """Decorator to register a fixture function."""
    def wrap(fn):
        FIXTURES.append({
            "rule_id": rule_id,
            "filename": filename,
            "description": description,
            "builder": fn,
        })
        return fn
    return wrap


@fixture("NAMING-001", "naming_001_non_pascal_global.ppxml",
         "Global property assigned with a non-PascalCase name.")
def _naming_001():
    c1 = _component(
        local_id=1, display_name="Bad Global Write",
        expression="@myBadGlobal := 'hello';"
    )
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="NamingOneFixture",
        declare_global="myBadGlobal",   # declare it so SCOPE-001 doesn't also fire
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("NAMING-002", "naming_002_non_camel_local.ppxml",
         "Local property assigned with a non-camelCase name.")
def _naming_002():
    c1 = _component(
        local_id=1, display_name="Bad Local Write",
        expression="#BadLocal := 1;"
    )
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="NamingTwoFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("NAMING-003", "naming_003_underscored_protocol.ppxml",
         "Protocol name uses underscores instead of spaces.")
def _naming_003():
    comps, conns = _clean_two_component_chain()
    return _protocol(
        name="Underscored_Protocol_Name",
        components=comps,
        connections=conns,
    )


@fixture("LAYOUT-001", "layout_001_disabled_component.ppxml",
         "A component left in the protocol with ComponentDisabled != 0.")
def _layout_001():
    c1 = _component(local_id=1, display_name="Active Step", expression="x := 1;")
    c2 = _component(local_id=2, display_name="Disabled Step",
                    disabled=4, expression="y := 2;")
    c3 = _no_op_sink(local_id=3)
    return _protocol(
        name="LayoutOneFixture",
        components=[c1, c2, c3],
        connections=[_connection(1, 2), _connection(2, 3)],
    )


@fixture("LAYOUT-002", "layout_002_unnamed_generic.ppxml",
         "Custom Manipulator left with its default display name empty.")
def _layout_002():
    c1 = _component(local_id=1, display_name="", expression="x := 1;")
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="LayoutTwoFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("LAYOUT-003", "layout_003_unused_pass_port.ppxml",
         "Component declares both ports, has a fail connection, but no pass connection.")
def _layout_003():
    # c1 has both ports declared, routes only to fail
    c1 = _component(
        local_id=1, display_name="Only Fail Connected",
        attributes=("ComponentTakesInput", "ComponentReturnsPass", "ComponentReturnsFail"),
        expression="x := 1;",
    )
    c2 = _component(local_id=2, display_name="Upstream", expression="y := 2;")
    c3 = _no_op_sink(local_id=3)
    # 2 -> 1 (input); 1 -> 3 via fail port only (no pass connection from 1)
    conns = [_connection(2, 1), _connection(1, 3, port="false")]
    return _protocol(
        name="LayoutThreeFixture",
        components=[c1, c2, c3],
        connections=conns,
    )


@fixture("LAYOUT-004", "layout_004_unused_fail_port.ppxml",
         "Component declares both ports, has pass connection but no fail connection.")
def _layout_004():
    c1 = _component(
        local_id=1, display_name="Only Pass Connected",
        attributes=("ComponentTakesInput", "ComponentReturnsPass", "ComponentReturnsFail"),
        expression="x := 1;",
    )
    c2 = _component(local_id=2, display_name="Upstream", expression="y := 2;")
    c3 = _no_op_sink(local_id=3)
    conns = [_connection(2, 1), _connection(1, 3, port="true")]
    return _protocol(
        name="LayoutFourFixture",
        components=[c1, c2, c3],
        connections=conns,
    )


@fixture("LAYOUT-005", "layout_005_dead_end_component.ppxml",
         "A non-terminal component receives data but has no outgoing connections.")
def _layout_005():
    c1 = _component(local_id=1, display_name="Upstream", expression="x := 1;")
    # c2 is a Custom Manipulator (not a terminal type) that receives but doesn't send
    c2 = _component(local_id=2, display_name="Dead End", expression="y := 2;")
    return _protocol(
        name="LayoutFiveFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],  # only inbound, no outbound from c2
    )


@fixture("LAYOUT-006", "layout_006_orphaned_component.ppxml",
         "A component not connected to any other.")
def _layout_006():
    c1 = _component(local_id=1, display_name="First", expression="x := 1;")
    c2 = _no_op_sink(local_id=2)
    # c3 is orphaned (no connection references it) — this is the target
    c3 = _component(local_id=3, display_name="Lonely", expression="z := 3;")
    return _protocol(
        name="LayoutSixFixture",
        components=[c1, c2, c3],
        connections=[_connection(1, 2)],
    )


@fixture("LAYOUT-007", "layout_007_todo_sticky_note.ppxml",
         "A sticky note contains 'TODO' / 'need to' language.")
def _layout_007():
    comps, conns = _clean_two_component_chain()
    return _protocol(
        name="LayoutSevenFixture",
        sticky_note="TODO: need to add validation logic here before going live.",
        components=comps,
        connections=conns,
    )


@fixture("LAYOUT-008", "layout_008_todo_in_pilotscript.ppxml",
         "A PilotScript expression contains TODO/FIXME language.")
def _layout_008():
    c1 = _component(
        local_id=1, display_name="Has TODO",
        expression="x := 1;\n/* TODO: handle the error case here */\ny := 2;"
    )
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="LayoutEightFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("LAYOUT-009", "layout_009_duplicate_log_messages.ppxml",
         "Two Application Log components share identical message + filename.")
def _layout_009():
    # Upstream feeder
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")

    # Application Log takes extra args: Message and Filename
    log_extra_1 = [
        _arg("Message", "logMsg := 'identical payload';", "ExpressionType"),
        _arg("Filename", "app_log.txt"),
    ]
    log_extra_2 = [
        _arg("Message", "logMsg := 'identical payload';", "ExpressionType"),
        _arg("Filename", "app_log.txt"),
    ]
    log1 = _component(
        object_type="SciTegic.ApplicationLog.1",
        component_name="Application Log",
        local_id=2, display_name="Log Alpha",
        derived_from="Application Log",
        attributes=("ComponentTakesInput",),
        expression=None,
        extra_args=log_extra_1,
    )
    log2 = _component(
        object_type="SciTegic.ApplicationLog.1",
        component_name="Application Log",
        local_id=3, display_name="Log Beta",
        derived_from="Application Log",
        attributes=("ComponentTakesInput",),
        expression=None,
        extra_args=log_extra_2,
    )
    return _protocol(
        name="LayoutNineFixture",
        components=[feeder, log1, log2],
        # Both logs connected to the feeder to avoid orphaned warnings
        connections=[_connection(1, 2), _connection(1, 3)],
    )


@fixture("SCOPE-001", "scope_001_undeclared_global.ppxml",
         "A global is assigned but never declared in DeclareGlobal or DeclareLocal.")
def _scope_001():
    c1 = _component(
        local_id=1, display_name="Writes Undeclared",
        expression="@UndeclaredGlobal := 'value';"
    )
    c2 = _no_op_sink(local_id=2)
    # No DeclareGlobal, no DeclareLocal on any component
    return _protocol(
        name="ScopeOneFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("SCOPE-002", "scope_002_cache_not_job_scope.ppxml",
         "A Cache Writer uses 'Shared' scope instead of 'Job Only'.")
def _scope_002():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    cache_extras = [
        # Use a $(...) tokenised ID so SCOPE-003 (hardcoded cache id)
        # doesn't also fire. SCOPE-002 is purely about the scope value.
        _arg("CacheID", "$(TempCacheName)"),
        _legalval_arg("Scope", {"Shared"}, ("Job Only", "User Only", "Shared")),
    ]
    cache = _component(
        object_type="SciTegic.DataCacheIO.1",
        component_name="Cache Writer",
        local_id=2, display_name="Wide Scope Cache",
        derived_from="Cache Writer",
        attributes=("ComponentTakesInput",),
        expression=None,
        extra_args=cache_extras,
    )
    return _protocol(
        name="ScopeTwoFixture",
        components=[feeder, cache],
        connections=[_connection(1, 2)],
    )


@fixture("SCOPE-003", "scope_003_hardcoded_cache_id.ppxml",
         "A Cache Writer uses a literal CacheID rather than a $(Temp...) token.")
def _scope_003():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    cache_extras = [
        _arg("CacheID", "HardcodedCacheName"),
        _legalval_arg("Scope", {"Job Only"}, ("Job Only", "User Only", "Shared")),
    ]
    cache = _component(
        object_type="SciTegic.DataCacheIO.1",
        component_name="Cache Writer",
        local_id=2, display_name="Literal Cache ID",
        derived_from="Cache Writer",
        attributes=("ComponentTakesInput",),
        expression=None,
        extra_args=cache_extras,
    )
    return _protocol(
        name="ScopeThreeFixture",
        components=[feeder, cache],
        connections=[_connection(1, 2)],
    )


@fixture("SCOPE-004", "scope_004_subprotocol_no_declare_local.ppxml",
         "A subprotocol assigns a global without DeclareLocal.")
def _scope_004():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    subproto = _component(
        object_type="SciTegic.Protocol.1",
        component_name="Subprotocol",
        local_id=2,
        display_name="Leaky Subprotocol",
        derived_from="SubProtocol",
        attributes=("ComponentTakesInput", "ComponentReturnsPass"),
        expression=None,
        initial_expression="@LeakedGlobal := 'leaked';",
    )
    sink = _no_op_sink(local_id=3)
    return _protocol(
        name="ScopeFourFixture",
        # Declare the global at protocol level so SCOPE-001 doesn't also fire.
        declare_global="LeakedGlobal",
        components=[feeder, subproto, sink],
        connections=[_connection(1, 2), _connection(2, 3)],
    )


@fixture("ERROR-001", "error_001_http_halt.ppxml",
         "HTTP Connector with OnGeneralError = Halt.")
def _error_001():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    http_extras = [
        _legalval_arg("OnGeneralError", {"Halt"}, ("Halt", "Fail", "Pass")),
        _arg("Source", "https://api.example.com/endpoint"),
    ]
    http = _component(
        object_type="SciTegic.HttpPost.1",
        component_name="HTTP Connector",
        local_id=2, display_name="Risky API Call",
        derived_from="HTTP Connector",
        attributes=("ComponentTakesInput", "ComponentReturnsPass", "ComponentReturnsFail"),
        expression=None,
        extra_args=http_extras,
    )
    # Make sure both ports are "connected" so LAYOUT-003/004 don't also fire
    sink_pass = _no_op_sink(local_id=3)
    sink_fail = _no_op_sink(local_id=4)
    conns = [
        _connection(1, 2),
        _connection(2, 3, port="true"),
        _connection(2, 4, port="false"),
    ]
    return _protocol(
        name="ErrorOneFixture",
        components=[feeder, http, sink_pass, sink_fail],
        connections=conns,
    )


@fixture("PSCRIPT-001", "pscript_001_hierarchical_percent.ppxml",
         "Expression uses %'/path' instead of Property('/path').")
def _pscript_001():
    c1 = _component(
        local_id=1, display_name="Bad Hierarchical Access",
        expression="material := %'//results/material';"
    )
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="PscriptOneFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("PSCRIPT-002", "pscript_002_filter_no_defined_check.ppxml",
         "Custom Filter compares a property without an 'is defined' guard. "
         "(Note: this rule currently has a bug that makes it never fire; "
         "this fixture will trigger it once the bug is fixed.)")
def _pscript_002():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    filt = _component(
        component_name="Custom Filter (PilotScript)",
        derived_from="Custom Filter (PilotScript)",
        local_id=2, display_name="Unguarded Filter",
        attributes=("ComponentTakesInput", "ComponentReturnsPass", "ComponentReturnsFail"),
        expression="Plant = '0006';",
    )
    sink_p = _no_op_sink(local_id=3)
    sink_f = _no_op_sink(local_id=4)
    return _protocol(
        name="PscriptTwoFixture",
        components=[feeder, filt, sink_p, sink_f],
        connections=[
            _connection(1, 2),
            _connection(2, 3, port="true"),
            _connection(2, 4, port="false"),
        ],
    )


@fixture("PSCRIPT-003", "pscript_003_long_elsif_chain.ppxml",
         "Expression with 4+ elsif branches.")
def _pscript_003():
    long_chain = (
        "if Material = 'A' then Template := 'RL';\n"
        "elsif Material = 'B' then Template := 'RL';\n"
        "elsif Material = 'C' then Template := 'RL';\n"
        "elsif Material = 'D' then Template := 'RL';\n"
        "elsif Material = 'E' then Template := 'RL';\n"
        "elsif Material = 'F' then Template := 'RL';\n"
        "end if;"
    )
    c1 = _component(local_id=1, display_name="Big If Chain", expression=long_chain)
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="PscriptThreeFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("PSCRIPT-004", "pscript_004_hardcoded_array.ppxml",
         "Filter uses a large hardcoded array literal.")
def _pscript_004():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    # Use Custom Filter so check_hardcoded_array_literals picks it up,
    # but without reusing PSCRIPT-002's exact pattern.
    filt = _component(
        component_name="Custom Filter (PilotScript)",
        derived_from="Custom Filter (PilotScript)",
        local_id=2, display_name="Hardcoded List",
        attributes=("ComponentTakesInput", "ComponentReturnsPass", "ComponentReturnsFail"),
        expression=(
            "Material is defined and "
            "contains(array('AAA','BBB','CCC','DDD','EEE','FFF'), Material);"
        ),
    )
    sink_p = _no_op_sink(local_id=3)
    sink_f = _no_op_sink(local_id=4)
    return _protocol(
        name="PscriptFourFixture",
        components=[feeder, filt, sink_p, sink_f],
        connections=[
            _connection(1, 2),
            _connection(2, 3, port="true"),
            _connection(2, 4, port="false"),
        ],
    )


@fixture("PROTO-001", "proto_001_locally_modified_subprotocol.ppxml",
         "Subprotocol flagged as locally modified (SubProtocolModified=1).")
def _proto_001():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    subproto = _component(
        object_type="SciTegic.Protocol.1",
        component_name="Subprotocol",
        local_id=2, display_name="Modified Subproto",
        derived_from="SubProtocol",
        attributes=("ComponentTakesInput", "ComponentReturnsPass"),
        expression=None,
        extra_args=[_arg("SubProtocolModified", "1", "BoolType")],
    )
    sink = _no_op_sink(local_id=3)
    return _protocol(
        name="ProtoOneFixture",
        components=[feeder, subproto, sink],
        connections=[_connection(1, 2), _connection(2, 3)],
    )


@fixture("PROTO-002", "proto_002_no_help_text.ppxml",
         "Protocol has no meaningful help text at protocol level.")
def _proto_002():
    comps, conns = _clean_two_component_chain()
    # help_text="" causes _protocol() to write only placeholder values
    # ("100", "None") which the linter filters out as meaningless.
    return _protocol(
        name="ProtoTwoFixture",
        help_text="",
        components=comps,
        connections=conns,
    )


@fixture("APPDEV-001", "appdev_001_dev_path.ppxml",
         "Protocol stored under a DEV path.")
def _appdev_001():
    comps, conns = _clean_two_component_chain()
    return _protocol(
        name="AppdevOneFixture",
        path="Protocols\\DEV\\Someone\\AppdevOneFixture",
        components=comps,
        connections=conns,
    )


@fixture("GUID-001", "guid_001_no_guid.ppxml",
         "Protocol has no ComponentGUID.")
def _guid_001():
    comps, conns = _clean_two_component_chain()
    return _protocol(
        name="GuidOneFixture",
        guid="",
        components=comps,
        connections=conns,
    )


@fixture("INTEG-001", "integ_001_hardcoded_source_path.ppxml",
         "Component Source parameter contains a UNC path.")
def _integ_001():
    # Reader with a Source param that's a UNC path
    reader_extras = [_arg("Source", "\\\\fileserver\\share\\input.xlsx")]
    reader = _component(
        object_type="SciTegic.PropertyFunctions.1",
        component_name="Excel Reader",
        local_id=1, display_name="Reads From UNC",
        derived_from="Excel Reader",
        attributes=("ComponentReturnsPass",),
        expression=None,
        extra_args=reader_extras,
    )
    sink = _no_op_sink(local_id=2)
    return _protocol(
        name="IntegOneFixture",
        components=[reader, sink],
        connections=[_connection(1, 2)],
    )


@fixture("INTEG-002", "integ_002_hardcoded_url.ppxml",
         "PilotScript expression contains a hardcoded http(s) URL.")
def _integ_002():
    c1 = _component(
        local_id=1, display_name="Hardcoded URL",
        expression="endpoint := 'https://api.prod.example.com/v1/data';"
    )
    c2 = _no_op_sink(local_id=2)
    return _protocol(
        name="IntegTwoFixture",
        components=[c1, c2],
        connections=[_connection(1, 2)],
    )


@fixture("SEC-001", "sec_001_embedded_credentials.ppxml",
         "HTTP Connector with username and password embedded.")
def _sec_001():
    feeder = _component(local_id=1, display_name="Feeder", expression="x := 1;")
    http_extras = [
        _legalval_arg("OnGeneralError", {"Fail"}, ("Halt", "Fail", "Pass")),
        _arg("Source", "https://api.example.com/endpoint"),
        _arg("Username", "svc_account"),
        _arg("Password", "encryptedPasswordBlob=="),
    ]
    http = _component(
        object_type="SciTegic.HttpPost.1",
        component_name="HTTP Connector",
        local_id=2, display_name="Authed Call",
        derived_from="HTTP Connector",
        attributes=("ComponentTakesInput", "ComponentReturnsPass", "ComponentReturnsFail"),
        expression=None,
        extra_args=http_extras,
    )
    sink_p = _no_op_sink(local_id=3)
    sink_f = _no_op_sink(local_id=4)
    return _protocol(
        name="SecOneFixture",
        components=[feeder, http, sink_p, sink_f],
        connections=[
            _connection(1, 2),
            _connection(2, 3, port="true"),
            _connection(2, 4, port="false"),
        ],
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def generate_all(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    results = []
    for fx in FIXTURES:
        xml = fx["builder"]()
        path = os.path.join(output_dir, fx["filename"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        results.append((fx["rule_id"], fx["filename"], fx["description"]))
    return results


if __name__ == "__main__":
    out = "test_fixtures"
    results = generate_all(out)
    print(f"Generated {len(results)} fixtures in {out}/")
    for rule_id, filename, desc in results:
        print(f"  [{rule_id}] {filename}")
