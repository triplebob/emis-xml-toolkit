import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Any, List, Optional
from html import escape
import streamlit as st
import streamlit.components.v1 as components
from ...theme import info_box
from ...tab_helpers import build_folder_option_list
from ....caching.search_cache import get_selected_search_id, set_selected_search_id


def render_raw_viewer(xml_content: str, nodes: List[Dict[str, Any]], folders: List[Dict[str, Any]]):
    if not xml_content:
        st.markdown(info_box("No XML content loaded."), unsafe_allow_html=True)
        return

    if not nodes:
        st.markdown(info_box("No searches or reports detected in this XML."), unsafe_allow_html=True)
        return

    st.subheader("📂 Select XML element")

    # Get currently selected search from session state (for cross-tab persistence)
    current_search_id = get_selected_search_id()
    current_node = None
    current_folder_id = None

    # Find the node matching the current selection
    if current_search_id:
        for n in nodes:
            if n.get("id") == current_search_id:
                current_node = n
                current_folder_id = n.get("folder_id")
                break

    # Default folder selection to current node's folder or "All folders"
    folder_options = build_folder_option_list(nodes, folders, all_label="All Folders inc Root")
    default_folder_idx = 0
    if current_folder_id:
        for idx, option in enumerate(folder_options):
            if option["value"] == current_folder_id:
                default_folder_idx = idx
                break

    selected_folder_id: Optional[str] = None
    col1, col2 = st.columns([2, 3])
    with col1:
        selected_folder = st.selectbox(
            "📁 Folder",
            options=folder_options,
            format_func=lambda opt: opt["label"],
            index=default_folder_idx,
            key="xml_folder_selector",
        )
        if selected_folder and selected_folder["value"] != "__all__":
            selected_folder_id = selected_folder["value"]

    # Filter nodes by selected folder (if chosen)
    filtered = [n for n in nodes if (not selected_folder_id or n.get("folder_id") == selected_folder_id)]
    if not filtered:
        st.markdown(info_box("No items in the selected folder."), unsafe_allow_html=True)
        return

    node_lookup = {n.get("id"): n for n in filtered if n.get("id")}

    def _label(node_id: str) -> str:
        node = node_lookup.get(node_id, {})
        name = node.get("name") or node.get("id") or "Unnamed"
        t = node.get("type_label") or node.get("source_type") or ""
        return f"[{t}] {name}"

    # Find default index for search selection
    sorted_filtered = sorted(node_lookup.keys(), key=_label)
    default_search_idx = 0
    if current_node and current_node.get("id") in node_lookup:
        try:
            default_search_idx = sorted_filtered.index(current_node.get("id"))
        except ValueError:
            pass

    with col2:
        selection_id = st.selectbox(
            "🔍 Search/Report",
            options=sorted_filtered,
            format_func=_label,
            index=default_search_idx,
            key="xml_search_selector",
        )
        selection = node_lookup.get(selection_id)

    # Update session state when selection changes
    if selection and selection.get("id") != current_search_id:
        set_selected_search_id(selection.get("id"))

    if selection:
        _render_fragment_fragment(xml_content, selection)


def _extract_element(xml_content: str, element_id: str) -> str:
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return ""

    candidates = list(root.findall(".//{*}report"))
    candidates += list(root.findall(".//{*}search"))

    for elem in candidates:
        cid = elem.findtext(".//{*}id")
        if cid == element_id:
            return ET.tostring(elem, encoding="unicode")
    return ""


@st.fragment
def _render_fragment_fragment(xml_content: str, selection: Dict[str, Any]):
    element_id = selection.get("id")
    raw_fragment = _extract_element(xml_content, element_id)
    if not raw_fragment:
        st.markdown(info_box("Unable to locate XML fragment for this item."), unsafe_allow_html=True)
        return

    # Style for consistent font sizes and green values
    st.markdown("""
        <style>
        .xml-info-item {
            font-size: 1rem;
            line-height: 1.5;
        }
        .xml-info-item .xml-value {
            color: #4EC9B0;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 1.05rem;
        }
        </style>
    """, unsafe_allow_html=True)

    etype = selection.get("type_label") or selection.get("source_type") or ""
    name = selection.get("name") or selection.get("id") or "Unnamed"
    name_label = "Search Name" if "search" in etype.lower() else "Report Name"

    col1, col2, col3, col_toggle = st.columns([3, 1.8, 3, 1.5])

    with col1:
        st.markdown(f'<div class="xml-info-item"><strong>Element GUID:</strong>&nbsp;&nbsp;<span class="xml-value">{element_id}</span></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="xml-info-item"><strong>Element Type:</strong>&nbsp;&nbsp;<span class="xml-value">{etype or "N/A"}</span></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="xml-info-item"><strong>{name_label}:</strong>&nbsp;&nbsp;<span class="xml-value">{name}</span></div>', unsafe_allow_html=True)
    with col_toggle:
        strip_ns = not st.checkbox(
            "Show Namespaces",
            value=False,
            help="Include namespace prefixes (e.g., ns0) when displaying the selected element",
        )

    pretty = _prettify_xml(raw_fragment, strip_namespaces=strip_ns)
    _render_pretty_xml(pretty)


def _prettify_xml(fragment: str, strip_namespaces: bool = True) -> str:
    try:
        if strip_namespaces:
            def _strip_ns(elem):
                elem.tag = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
                for child in list(elem):
                    _strip_ns(child)
            elem = ET.fromstring(fragment)
            _strip_ns(elem)
            fragment = ET.tostring(elem, encoding="unicode")

        parsed = minidom.parseString(fragment)
        pretty = parsed.toprettyxml(indent="  ")
        lines = [line for line in pretty.splitlines() if line.strip()]
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        return "\n".join(lines)
    except Exception:
        return fragment


def _render_pretty_xml(pretty: str, show_line_numbers: bool = True):
    """
    Render XML with highlight.js from CDN. Falls back to st.code if anything fails.
    """
    try:
        escaped = escape(pretty)
        show_lines_js = "true" if show_line_numbers else "false"

        html_block = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
            body {{
                margin: 0;
                padding: 4px;
                background-color: #1E1E1E;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                height: 100vh;
                overflow: hidden;
            }}
            .xml-container {{
                border: 1px solid #404040;
                border-radius: 0.5rem;
                height: calc(100vh - 10px);
                overflow: auto;
                background-color: #1E1E1E;
            }}
            /* Hidden pre for highlight.js processing */
            #source-code {{
                position: absolute;
                left: -9999px;
            }}
            /* Table-based line display */
            .code-table {{
                border-collapse: collapse;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 15px;
                line-height: 1.6;
                margin: 12px;
            }}
            .code-table td {{
                padding: 0;
                vertical-align: top;
            }}
            .code-table .line-num {{
                width: 3.5em;
                padding-right: 1em;
                text-align: right;
                color: #6e7681;
                border-right: 1px solid #404040;
                user-select: none;
                -webkit-user-select: none;
                -moz-user-select: none;
                -ms-user-select: none;
            }}
            .code-table .line-code {{
                padding-left: 1em;
                white-space: pre;
                color: #D4D4D4;
            }}
            /* VS2015 dark theme syntax colors */
            .hljs-comment {{ color: #6A9955; font-style: italic; }}
            .hljs-tag {{ color: #808080; }}
            .hljs-name {{ color: #569CD6; }}
            .hljs-attr {{ color: #9CDCFE; }}
            .hljs-string {{ color: #CE9178; }}
            .hljs-keyword {{ color: #569CD6; }}
            .hljs-literal {{ color: #569CD6; }}
            .hljs-number {{ color: #B5CEA8; }}
            .hljs-built_in {{ color: #4EC9B0; }}
            .hljs-symbol {{ color: #569CD6; }}
            .hljs-meta {{ color: #9B9B9B; }}
            </style>
        </head>
        <body>
            <div class="xml-container">
                <pre id="source-code"><code id="code-block" class="language-xml">{escaped}</code></pre>
                <table class="code-table" id="code-table"></table>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
            <script>
                function buildCodeTable() {{
                    var codeBlock = document.getElementById('code-block');
                    var table = document.getElementById('code-table');
                    var html = codeBlock.innerHTML;
                    var lines = html.split('\\n');
                    var showLines = {show_lines_js};

                    var tableHtml = '';
                    for (var i = 0; i < lines.length; i++) {{
                        var lineNum = showLines ? '<td class="line-num">' + (i + 1) + '</td>' : '';
                        tableHtml += '<tr>' + lineNum + '<td class="line-code">' + lines[i] + '</td></tr>';
                    }}
                    table.innerHTML = tableHtml;
                }}

                // Wait for highlight.js to load
                function init() {{
                    if (typeof hljs !== 'undefined') {{
                        hljs.highlightElement(document.getElementById('code-block'));
                        buildCodeTable();
                    }} else {{
                        setTimeout(init, 50);
                    }}
                }}
                init();
            </script>
        </body>
        </html>
        """
        # Dynamic height: fit content if small, fixed height with scroll if large
        num_lines = pretty.count("\n") + 1
        line_height_px = 24  # 15px font-size * 1.6 line-height
        max_lines_before_scroll = 30
        # Add extra height for: body padding (8px) + pre border (2px) + pre padding (24px) = 34px, plus buffer = 45px
        height_offset = 45

        if num_lines <= max_lines_before_scroll:
            # Fit to content (no scrollbar needed)
            height = min(800, height_offset + int(num_lines * line_height_px))
            scrolling = False
        else:
            # Fixed height with scrollbar for large content
            height = 800
            scrolling = True

        components.html(html_block, height=height, scrolling=scrolling)
    except Exception:
        st.code(pretty, language="xml")
