"""
UI utilities for the EMIS XML Converter application
Provides reusable Streamlit components and visualization patterns
"""

from .rendering_utils import (
    render_info_box,
    render_metric_card,
    render_expandable_section,
    create_two_column_layout,
    create_three_column_layout,
    create_tabs_layout,
    apply_custom_styling,
    render_data_table,
    render_progress_indicator,
    render_status_badge,
    render_classification_badge,
    render_collapsible_content,
    render_two_column_metrics,
    create_navigation_selectbox,
    render_section_header,
    render_debug_section,
    create_action_buttons_row
)

from .layout_utils import (
    NavigationManager,
    DataRenderer,
    StepRenderer,
    TreeRenderer
)

# Import functions from moved UI modules - during refactoring, use fallback imports
try:
    # Try new modular structure first
    from .tabs import render_results_tabs, render_xml_structure_tabs
except ImportError:
    # Fallback to original ui_tabs during transition
    from .ui_tabs import render_xml_structure_tabs, render_results_tabs

from .status_bar import render_status_bar
from .ui_helpers import render_info_section

# Import optimized UI components
from .progressive_loader import (
    get_progressive_loader,
    progressive_component,
    create_lazy_dataframe_renderer,
    create_lazy_metrics_renderer,
    monitor_component_performance,
    clear_progressive_cache
)
from .async_components import (
    get_async_tab_renderer,
    get_async_dataframe_renderer,
    async_tab_content,
    render_async_metrics,
    display_async_performance_dashboard,
    create_cancel_button
)

__all__ = [
    # Rendering utilities
    'render_info_box',
    'render_metric_card', 
    'render_expandable_section',
    'create_two_column_layout',
    'create_three_column_layout',
    'create_tabs_layout',
    'apply_custom_styling',
    'render_data_table',
    'render_progress_indicator',
    'render_status_badge',
    'render_classification_badge',
    'render_collapsible_content',
    'render_two_column_metrics',
    'create_navigation_selectbox',
    'render_section_header',
    'render_debug_section',
    'create_action_buttons_row',
    
    # Layout utilities
    'NavigationManager',
    'DataRenderer', 
    'StepRenderer',
    'TreeRenderer',
    
    # UI modules
    'render_xml_structure_tabs',
    'render_results_tabs',
    'render_status_bar',
    'render_info_section',
    
    # Progressive loading
    'get_progressive_loader',
    'progressive_component',
    'create_lazy_dataframe_renderer',
    'create_lazy_metrics_renderer',
    'monitor_component_performance',
    'clear_progressive_cache',
    
    # Async components
    'get_async_tab_renderer',
    'get_async_dataframe_renderer',
    'async_tab_content',
    'render_async_metrics',
    'display_async_performance_dashboard',
    'create_cancel_button'
]
