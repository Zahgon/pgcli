import logging

from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.filters import Condition
from prompt_toolkit.application import get_app
from .packages.parseutils.utils import is_open_quote

_logger = logging.getLogger(__name__)


def _is_complete(sql):
    # A complete command is an sql statement that ends with a semicolon, unless
    # there's an open quote surrounding it, as is common when writing a
    # CREATE FUNCTION command
    return sql.endswith(";") and not is_open_quote(sql)


"""
Returns True if the buffer contents should be handled (i.e. the query/command
executed) immediately. This is necessary as we use prompt_toolkit in multiline
mode, which by default will insert new lines on Enter.
"""


def safe_multi_line_mode(pgcli):

    return cond


def buffer_should_be_handled(pgcli):

    return cond
