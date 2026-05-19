import threading
import os
from collections import OrderedDict

from .pgcompleter import PGCompleter


class CompletionRefresher:
    refreshers = OrderedDict()

    def __init__(self):
        self._completer_thread = None
        self._restart_refresh = threading.Event()

    def refresh(self, executor, special, callbacks, history=None, settings=None):
        """
        Creates a PGCompleter object and populates it with the relevant
        completion suggestions in a background thread.

        executor - PGExecute object, used to extract the credentials to connect
                   to the database.
        special - PGSpecial object used for creating a new completion object.
        settings - dict of settings for completer object
        callbacks - A function or a list of functions to call after the thread
                    has completed the refresh. The newly created completion
                    object will be passed in as an argument to each callback.
        """
        if executor.is_virtual_database():
            # do nothing
            return [(None, None, None, "Auto-completion refresh can't be started.")]

        if self.is_refreshing():
            self._restart_refresh.set()
            return [(None, None, None, "Auto-completion refresh restarted.")]
        else:
            self._completer_thread = threading.Thread(
                target=self._bg_refresh,
                args=(executor, special, callbacks, history, settings),
                name="completion_refresh",
            )
            self._completer_thread.daemon = True
            self._completer_thread.start()
            return [(None, None, None, "Auto-completion refresh started in the background.")]

    def is_refreshing(self):
        return self._completer_thread and self._completer_thread.is_alive()



def refresher(name, refreshers=CompletionRefresher.refreshers):
    """Decorator to populate the dictionary of refreshers with the current
    function.
    """


    return wrapper














