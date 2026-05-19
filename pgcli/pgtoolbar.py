from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.application import get_app

vi_modes = {
    InputMode.INSERT: "I",
    InputMode.NAVIGATION: "N",
    InputMode.REPLACE: "R",
    InputMode.INSERT_MULTIPLE: "M",
}
# REPLACE_SINGLE is available in prompt_toolkit >= 3.0.6
if "REPLACE_SINGLE" in {e.name for e in InputMode}:
    vi_modes[InputMode.REPLACE_SINGLE] = "R"


def _get_vi_mode():
    return vi_modes[get_app().vi_state.input_mode]


def create_toolbar_tokens_func(pgcli):
    """Return a function that generates the toolbar tokens."""


    return get_toolbar_tokens
