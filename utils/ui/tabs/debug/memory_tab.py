"""
Memory Diagnostics Tab - Debug mode only.
Comprehensive visualisation of memory usage across session state, caches, and objects.
"""

import streamlit as st
import sys
import gc
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
from ....system.session_state import SessionStateKeys
from ...theme import success_box, ThemeSpacing


def _get_deep_size(obj: Any, seen: set = None, max_depth: int = 10) -> int:
    """Recursively calculate object size in bytes with depth limit."""
    if max_depth <= 0:
        return sys.getsizeof(obj)

    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)

    try:
        if isinstance(obj, dict):
            size += sum(_get_deep_size(k, seen, max_depth - 1) + _get_deep_size(v, seen, max_depth - 1) for k, v in obj.items())
        elif isinstance(obj, (list, tuple, set, frozenset)):
            size += sum(_get_deep_size(item, seen, max_depth - 1) for item in obj)
        elif hasattr(obj, '__dict__'):
            size += _get_deep_size(obj.__dict__, seen, max_depth - 1)
    except Exception:
        pass

    return size


def _format_bytes(size: int) -> str:
    """Format bytes to user-friendly string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _get_session_state_sizes() -> List[Tuple[str, int, str, int]]:
    """Get sizes of all session state keys with item counts."""
    sizes = []
    for key in st.session_state.keys():
        try:
            value = st.session_state[key]
            size = _get_deep_size(value)
            type_name = type(value).__name__

            # Get item count
            if isinstance(value, (list, dict, set)):
                count = len(value)
            elif hasattr(value, '__len__'):
                try:
                    count = len(value)
                except Exception:
                    count = -1
            else:
                count = -1

            sizes.append((key, size, type_name, count))
        except Exception:
            sizes.append((key, 0, "error", -1))

    # Sort by size descending
    sizes.sort(key=lambda x: x[1], reverse=True)
    return sizes


def _analyse_code_entry_structure(codes: List[Dict]) -> Dict[str, Any]:
    """Analyse the structure of code entries to find memory hogs."""
    if not codes:
        return {}

    analysis = {
        "total_codes": len(codes),
        "sample_keys": list(codes[0].keys()) if codes else [],
        "field_sizes": {},
        "has_debug_fields": False,
        "debug_fields_overhead": 0,
    }

    # Analyse field sizes across sample
    sample_size = min(100, len(codes))
    field_totals = defaultdict(int)

    for code in codes[:sample_size]:
        for key, value in code.items():
            field_totals[key] += _get_deep_size(value, max_depth=3)

        if "debug_fields" in code:
            analysis["has_debug_fields"] = True

    # Average per field
    analysis["field_sizes"] = {
        k: v // sample_size for k, v in sorted(field_totals.items(), key=lambda x: -x[1])
    }

    # Calculate debug_fields overhead
    if analysis["has_debug_fields"]:
        overhead_per_code = field_totals.get("debug_fields", 0) // sample_size
        analysis["debug_fields_overhead"] = overhead_per_code * len(codes)

    return analysis


def _analyse_dataframe(df, name: str) -> Dict[str, Any]:
    """Detailed DataFrame memory analysis."""
    if df is None:
        return {"name": name, "status": "None"}

    try:
        mem_usage = df.memory_usage(deep=True)
        total = mem_usage.sum()

        # Column breakdown
        columns = []
        for col in df.columns:
            col_mem = mem_usage.get(col, 0)
            columns.append({
                "column": col,
                "size": int(col_mem),
                "dtype": str(df[col].dtype),
                "pct": (col_mem / total * 100) if total > 0 else 0
            })

        columns.sort(key=lambda x: -x["size"])

        return {
            "name": name,
            "rows": len(df),
            "cols": len(df.columns),
            "total_memory": int(total),
            "index_memory": int(mem_usage.get("Index", 0)),
            "top_columns": columns[:10],
            "all_columns": columns,
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


def _get_streamlit_cache_stats() -> List[Dict[str, Any]]:
    """Attempt to get Streamlit cache statistics."""
    cache_stats = []

    # Known cached functions with their modules
    cached_funcs = [
        ("cache_parsed_xml", "utils.caching.xml_cache"),
        ("get_lookup_statistics", "utils.caching.lookup_manager"),
        ("create_lookup_dictionaries", "utils.caching.lookup_manager"),
        ("_build_snomed_lookup", "utils.ui.tabs.report_viewer.common"),
        ("_build_clinical_codes_cache", "utils.ui.tabs.search_browser.search_criteria_viewer"),
        ("translate_emis_to_snomed", "utils.metadata.snomed_translation"),
    ]

    for func_name, module_path in cached_funcs:
        try:
            # Try to import and check the function
            parts = module_path.split(".")
            module = __import__(module_path, fromlist=[parts[-1]])
            func = getattr(module, func_name, None)

            if func and hasattr(func, 'clear'):
                cache_stats.append({
                    "name": func_name,
                    "module": module_path,
                    "status": "active",
                    "clearable": True
                })
            else:
                cache_stats.append({
                    "name": func_name,
                    "module": module_path,
                    "status": "found (no clear)",
                    "clearable": False
                })
        except Exception as e:
            cache_stats.append({
                "name": func_name,
                "module": module_path,
                "status": f"error: {str(e)[:30]}",
                "clearable": False
            })

    return cache_stats


def _get_gc_stats() -> Dict[str, Any]:
    """Get garbage collector statistics."""
    gc.collect()

    stats = {
        "counts": gc.get_count(),
        "threshold": gc.get_threshold(),
        "objects_tracked": len(gc.get_objects()),
    }

    # Count objects by type
    type_counts = defaultdict(int)
    type_sizes = defaultdict(int)

    for obj in gc.get_objects():
        t = type(obj).__name__
        type_counts[t] += 1
        try:
            type_sizes[t] += sys.getsizeof(obj)
        except Exception:
            pass

    # Top types by count
    stats["top_types_by_count"] = sorted(type_counts.items(), key=lambda x: -x[1])[:15]
    stats["top_types_by_size"] = sorted(type_sizes.items(), key=lambda x: -x[1])[:15]

    return stats


def render_memory_content():
    """Render the memory diagnostics content."""
    # Hide Streamlit dataframe toolbar download icon in this tab; exports are controlled via explicit buttons.
    st.markdown("""<style>[data-testid="stElementToolbar"]{display: none;}</style>""", unsafe_allow_html=True)
    st.subheader("Memory Diagnostics")

    # ─────────────────────────────────────────────────────────────
    # SECTION 1: Process Memory Overview
    # ─────────────────────────────────────────────────────────────
    with st.expander("Process Memory", expanded=True):
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                with st.container(border=True):
                    st.metric("RSS (Resident)", _format_bytes(mem_info.rss),
                             help="Physical memory used by process")
            with col2:
                with st.container(border=True):
                    st.metric("VMS (Virtual)", _format_bytes(mem_info.vms),
                             help="Total virtual memory allocated")
            with col3:
                # Memory percent
                with st.container(border=True):
                    mem_pct = process.memory_percent()
                    st.metric("% System RAM", f"{mem_pct:.1f}%")
            with col4:
                with st.container(border=True):
                    gc_counts = gc.get_count()
                    st.metric("GC Generations", f"{gc_counts[0]}/{gc_counts[1]}/{gc_counts[2]}",
                             help="Objects in GC generation 0/1/2")

            # Additional memory info if available
            if hasattr(mem_info, 'uss'):
                st.caption(f"USS (Unique Set): {_format_bytes(mem_info.uss)} | "
                          f"Shared: {_format_bytes(mem_info.shared if hasattr(mem_info, 'shared') else 0)}")

        except ImportError:
            st.warning("Install psutil for detailed process memory stats: `pip install psutil`")
        except Exception as e:
            st.error(f"Error getting memory info: {e}")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # SECTION 2: Session State Breakdown
    # ─────────────────────────────────────────────────────────────
    with st.expander("Session State Breakdown", expanded=True):
        sizes = _get_session_state_sizes()
        total_size = sum(s[1] for s in sizes)

        col1, col2, col3 = st.columns(3)
        with col1:
            with st.container(border=True):
                st.metric("Total Size", _format_bytes(total_size))
        with col2:
            with st.container(border=True):
                st.metric("Keys", len(sizes))
        with col3:
            with st.container(border=True):
                top_5_pct = sum(s[1] for s in sizes[:5]) / total_size * 100 if total_size > 0 else 0
                st.metric("Top 5 Keys %", f"{top_5_pct:.1f}%")

        # Top consumers table
        st.markdown("#### Top 25 Session State Keys")

        if sizes:
            display_data = []
            for key, size, type_name, count in sizes[:25]:
                pct = (size / total_size * 100) if total_size > 0 else 0
                display_data.append({
                    "Key": key[:45] + "..." if len(key) > 45 else key,
                    "Size": _format_bytes(size),
                    "Type": type_name,
                    "Items": str(count) if count >= 0 else "-",
                    "%": f"{pct:.1f}%",
                })

            st.dataframe(display_data, hide_index=True, width="stretch")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # SECTION 3: Pipeline Code Analysis
    # ─────────────────────────────────────────────────────────────
    with st.expander("Pipeline Codes Analysis", expanded=True):
        codes = st.session_state.get(SessionStateKeys.PIPELINE_CODES, [])

        if codes and isinstance(codes, list):
            analysis = _analyse_code_entry_structure(codes)

            col1, col2, col3 = st.columns(3)
            with col1:
                with st.container(border=True):
                    st.metric("Total Codes", analysis.get("total_codes", 0))
                    st.markdown('<span class="metric-spacer">&nbsp;</span>', unsafe_allow_html=True)
            with col2:
                with st.container(border=True):
                    st.metric("Fields per Code", len(analysis.get("sample_keys", [])))
                    st.markdown('<span class="metric-spacer">&nbsp;</span>', unsafe_allow_html=True)
            with col3:
                with st.container(border=True):
                    if analysis.get("has_debug_fields"):
                        st.metric(
                            "Debug Fields",
                            "PRESENT",
                            delta=f"+{_format_bytes(analysis.get('debug_fields_overhead', 0))} overhead",
                            delta_color="inverse",
                        )
                    else:
                        st.metric("Debug Fields", "Not Present", delta="Memory optimised", delta_color="normal")

            # Field size breakdown
            if analysis.get("field_sizes"):
                st.markdown("#### Average Size per Field (per code entry)")

                field_data = []
                for field, avg_size in list(analysis["field_sizes"].items())[:20]:
                    total_est = avg_size * analysis["total_codes"]
                    field_data.append({
                        "Field": field[:40] + "..." if len(field) > 40 else field,
                        "Avg Size": _format_bytes(avg_size),
                        "Est. Total": _format_bytes(total_est),
                    })

                st.dataframe(field_data, hide_index=True, width="stretch")

        else:
            st.info("No pipeline codes loaded")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # SECTION 4: Lookup Table Analysis
    # ─────────────────────────────────────────────────────────────
    with st.expander("Lookup Table Analysis", expanded=True):
        from ....caching.lookup_manager import is_lookup_loaded, get_lookup_statistics
        if is_lookup_loaded():
            stats = get_lookup_statistics()
            encrypted_bytes = st.session_state.get(SessionStateKeys.LOOKUP_ENCRYPTED_BYTES)
            enc_size = len(encrypted_bytes) if encrypted_bytes else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                with st.container(border=True):
                    st.metric("Total Records", f"{stats.get('total_count', 0):,}")
            with col2:
                with st.container(border=True):
                    st.metric("Clinical Codes", f"{stats.get('clinical_count', 0):,}")
            with col3:
                with st.container(border=True):
                    st.metric("Encrypted Size", _format_bytes(enc_size))

            s_col1, s_col2, s_col3 = st.columns(3)
            with s_col1:
                with st.container(border=True):
                    st.metric("Medication Codes", f"{stats.get('medication_count', 0):,}")
            with s_col2:
                with st.container(border=True):
                    st.metric("Load Source", str(stats.get("load_source", "Unknown")))
            with s_col3:
                with st.container(border=True):
                    st.metric("EMIS Version", str(stats.get("emis_version", "Unknown")))
            st.markdown(
                success_box(
                    f"Extract Date: {stats.get('extract_date', 'Unknown')}",
                    margin_bottom=ThemeSpacing.MARGIN_EXTENDED,
                ),
                unsafe_allow_html=True,
            )
            st.markdown("")
        else:
            st.info("No lookup table loaded")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # SECTION 5: Streamlit Caches
    # ─────────────────────────────────────────────────────────────
    with st.expander("Streamlit Caches", expanded=True):
        cache_stats = _get_streamlit_cache_stats()

        cache_data = []
        for cache in cache_stats:
            cache_data.append({
                "Function": cache["name"],
                "Module": cache["module"].split(".")[-1],
                "Status": cache["status"],
            })

        st.dataframe(cache_data, hide_index=True, width="stretch")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # SECTION 6: Garbage Collector Stats
    # ─────────────────────────────────────────────────────────────
    with st.expander("Garbage Collector Details", expanded=True):
        gc_stats = _get_gc_stats()

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            with st.container(border=True):
                st.metric("Objects tracked", f"{gc_stats['objects_tracked']:,}")
        with m_col2:
            with st.container(border=True):
                st.metric("GC Thresholds", str(gc_stats["threshold"]))

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Top Types by Count:**")
            type_count_data = [{"Type": t, "Count": f"{c:,}"} for t, c in gc_stats["top_types_by_count"]]
            st.dataframe(type_count_data, hide_index=True, width="stretch")

        with col2:
            st.markdown("**Top Types by Size:**")
            type_size_data = [{"Type": t, "Size": _format_bytes(s)} for t, s in gc_stats["top_types_by_size"]]
            st.dataframe(type_size_data, hide_index=True, width="stretch")

    st.divider()

    # ─────────────────────────────────────────────────────────────
    # SECTION 7: Actions
    # ─────────────────────────────────────────────────────────────
    st.markdown("### Memory Actions")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🗑️ Force GC", width="stretch", help="Run garbage collection"):
            collected = gc.collect()
            st.success(f"Collected {collected} objects")
            st.rerun()

    with col2:
        if st.button("🧹 Clear Exports", width="stretch", help="Clear export caches"):
            from ....system.session_state import clear_export_state
            clear_export_state()
            st.success("Export caches cleared")
            st.rerun()

    with col3:
        if st.button("🔄 Clear Pipelines", width="stretch", help="Clear pipeline caches"):
            from ....system.session_state import clear_pipeline_caches
            clear_pipeline_caches()
            st.success("Pipeline caches cleared")
            st.rerun()

    with col4:
        if st.button("📊 Refresh Stats", width="stretch", help="Refresh this page"):
            st.rerun()
