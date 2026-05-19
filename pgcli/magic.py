from .main import PGCli
import sql.parse
import sql.connection
import logging

_logger = logging.getLogger(__name__)


def load_ipython_extension(ipython):
    """This is called via the ipython command '%load_ext pgcli.magic'"""
    pass


