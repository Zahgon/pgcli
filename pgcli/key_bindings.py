import logging
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import (
    completion_is_selected,
    is_searching,
    has_completions,
    has_selection,
    vi_mode,
)

from .pgbuffer import buffer_should_be_handled, safe_multi_line_mode

_logger = logging.getLogger(__name__)


def pgcli_bindings(pgcli):
    """Custom key bindings for pgcli."""
    kb = KeyBindings()

    tab_insert_text = " " * 4

    @kb.add("f2")
    def _(event):
        """Enable/Disable SmartCompletion Mode."""
        pass

    @kb.add("f3")
    def _(event):
        """Enable/Disable Multiline Mode."""
        pass

    @kb.add("f4")
    def _(event):
        """Toggle between Vi and Emacs mode."""
        pass

    @kb.add("f5")
    def _(event):
        """Toggle between Vi and Emacs mode."""
        pass

    @kb.add("tab")
    def _(event):
        """Force autocompletion at cursor on non-empty lines."""
        pass

    @kb.add("escape", filter=has_completions)
    def _(event):
        """Force closing of autocompletion."""
        pass

    @kb.add("c-space")
    def _(event):
        """
        Initialize autocompletion at cursor.

        If the autocompletion menu is not showing, display it with the
        appropriate completions for the context.

        If the menu is showing, select the next completion.
        """
        pass

    @kb.add("enter", filter=completion_is_selected)
    def _(event):
        """Makes the enter key work as the tab key only when showing the menu.

        In other words, don't execute query when enter is pressed in
        the completion dropdown menu, instead close the dropdown menu
        (accept current selection).

        """
        pass

    # When using multi_line input mode the buffer is not handled on Enter (a new line is
    # inserted instead), so we force the handling if we're not in a completion or
    # history search, and one of several conditions are True

    @kb.add("escape", "enter", filter=~vi_mode & ~safe_multi_line_mode(pgcli))
    def _(event):
        """Introduces a line break regardless of multi-line mode or not."""
        pass

    @kb.add("c-p", filter=~has_selection)
    def _(event):
        """Move up in history."""
        pass

    @kb.add("c-n", filter=~has_selection)
    def _(event):
        """Move down in history."""
        pass

    return kb
