"""ui_tui.render — layout + panel renderers + palette."""
from ui_tui.render.layout import build_layout
from ui_tui.render.panels import (
    render_chat_area,
    render_input_box,
    render_persona,
    render_status_bar,
    render_tool_log,
    render_working_process,
)
from ui_tui.render.palette import build_command_palette