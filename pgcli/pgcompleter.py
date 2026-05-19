import json
import logging
import re
from itertools import count, chain
import operator
from collections import namedtuple, defaultdict, OrderedDict
from cli_helpers.tabular_output import TabularOutputFormatter
from pgspecial.namedqueries import NamedQueries
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document
from .packages.sqlcompletion import (
    FromClauseItem,
    suggest_type,
    Special,
    Database,
    Schema,
    Table,
    TableFormat,
    Function,
    Column,
    View,
    Keyword,
    NamedQuery,
    Datatype,
    Alias,
    Path,
    JoinCondition,
    Join,
)
from .packages.parseutils.meta import ColumnMetadata, ForeignKey
from .packages.parseutils.utils import last_word
from .packages.parseutils.tables import TableReference
from .packages.pgliterals.main import get_literals
from .packages.prioritization import PrevalenceCounter

_logger = logging.getLogger(__name__)

Match = namedtuple("Match", ["completion", "priority"])

_SchemaObject = namedtuple("SchemaObject", "name schema meta")




_Candidate = namedtuple("Candidate", "completion prio meta synonyms prio2 display")




# Used to strip trailing '::some_type' from default-value expressions
arg_default_type_strip_regex = re.compile(r"::[\w\.]+(\[\])?$")


def normalize_ref(ref):
    return ref if ref[0] == '"' else '"' + ref.lower() + '"'


def generate_alias(tbl, alias_map=None):
    """Generate a table alias.

    Given a table name will return an alias for that table using the first of
    the following options there's a match for.

        1. The predefined alias for table defined in the alias_map.
        2. All upper-case letters in the table name.
        3. The first letter of the table name and all letters preceded by _

    :param tbl: unescaped name of the table to alias
    :param alias_map: optional mapping of predefined table aliases
    """
    if alias_map and tbl in alias_map:
        return alias_map[tbl]
    return "".join([l for l in tbl if l.isupper()] or [l for l, prev in zip(tbl, "_" + tbl) if prev == "_" and l != "_"])


class InvalidMapFile(ValueError):
    pass




class PGCompleter(Completer):
    # keywords_tree: A dict mapping keywords to well known following keywords.
    # e.g. 'CREATE': ['TABLE', 'USER', ...],
    keywords_tree = get_literals("keywords", type_=dict)
    keywords = tuple(set(chain(keywords_tree.keys(), *keywords_tree.values())))
    functions = get_literals("functions")
    datatypes = get_literals("datatypes")
    reserved_words = set(get_literals("reserved"))

    def __init__(self, smart_completion=True, pgspecial=None, settings=None):
        super().__init__()
        self.smart_completion = smart_completion
        self.pgspecial = pgspecial
        self.prioritizer = PrevalenceCounter()
        settings = settings or {}
        self.signature_arg_style = settings.get("signature_arg_style", "{arg_name} {arg_type}")
        self.call_arg_style = settings.get("call_arg_style", "{arg_name: <{max_arg_len}} := {arg_default}")
        self.call_arg_display_style = settings.get("call_arg_display_style", "{arg_name}")
        self.call_arg_oneliner_max = settings.get("call_arg_oneliner_max", 2)
        self.search_path_filter = settings.get("search_path_filter")
        self.generate_aliases = settings.get("generate_aliases")
        alias_map_file = settings.get("alias_map_file")
        if alias_map_file is not None:
            self.alias_map = load_alias_map_file(alias_map_file)
        else:
            self.alias_map = None
        self.casing_file = settings.get("casing_file")
        self.insert_col_skip_patterns = [
            re.compile(pattern) for pattern in settings.get("insert_col_skip_patterns", [r"^now\(\)$", r"^nextval\("])
        ]
        self.generate_casing_file = settings.get("generate_casing_file")
        self.qualify_columns = settings.get("qualify_columns", "if_more_than_one_table")
        self.asterisk_column_order = settings.get("asterisk_column_order", "table_order")

        keyword_casing = settings.get("keyword_casing", "upper").lower()
        if keyword_casing not in ("upper", "lower", "auto"):
            keyword_casing = "upper"
        self.keyword_casing = keyword_casing
        self.name_pattern = re.compile(r"^[_a-z][_a-z0-9\$]*$")

        self.databases = []
        self.dbmetadata = {"tables": {}, "views": {}, "functions": {}, "datatypes": {}}
        self.search_path = []
        self.casing = {}

        self.all_completions = set(self.keywords + self.functions)

    def escape_name(self, name):
        if name and ((not self.name_pattern.match(name)) or (name.upper() in self.reserved_words) or (name.upper() in self.functions)):
            name = '"%s"' % name

        return name


    def unescape_name(self, name):
        """Unquote a string."""
        if name and name[0] == '"' and name[-1] == '"':
            name = name[1:-1]

        return name

    def escaped_names(self, names):
        return [self.escape_name(name) for name in names]




    def extend_casing(self, words):
        """extend casing data

        :return:
        """
        pass

    def extend_relations(self, data, kind):
        """extend metadata for tables or views.

        :param data: list of (schema_name, rel_name) tuples
        :param kind: either 'tables' or 'views'

        :return:

        """
        pass

    def extend_columns(self, column_data, kind):
        """extend column metadata.

        :param column_data: list of (schema_name, rel_name, column_name,
        column_type, has_default, default) tuples
        :param kind: either 'tables' or 'views'

        :return:

        """
        pass





    def extend_query_history(self, text, is_init=False):
        if is_init:
            # During completer initialization, only load keyword preferences,
            # not names
            self.prioritizer.update_keywords(text)
        else:
            self.prioritizer.update(text)

    def set_search_path(self, search_path):
        self.search_path = self.escaped_names(search_path)

    def reset_completions(self):
        self.databases = []
        self.special_commands = []
        self.search_path = []
        self.dbmetadata = {"tables": {}, "views": {}, "functions": {}, "datatypes": {}}
        self.all_completions = set(self.keywords + self.functions)

    def find_matches(self, text, collection, mode="fuzzy", meta=None):
        """Find completion matches for the given text.

        Given the user's input text and a collection of available
        completions, find completions matching the last word of the
        text.

        `collection` can be either a list of strings or a list of Candidate
        namedtuples.
        `mode` can be either 'fuzzy', or 'strict'
            'fuzzy': fuzzy matching, ties broken by name prevalance
            `keyword`: start only matching, ties broken by keyword prevalance

        yields prompt_toolkit Completion instances for any matches found
        in the collection of available completions.

        """
        if not collection:
            return []
        prio_order = [
            "keyword",
            "function",
            "view",
            "table",
            "datatype",
            "database",
            "schema",
            "column",
            "table alias",
            "join",
            "name join",
            "fk join",
            "table format",
        ]
        type_priority = prio_order.index(meta) if meta in prio_order else -1
        text = last_word(text, include="most_punctuations").lower()
        text_len = len(text)

        if text and text[0] == '"':
            # text starts with double quote; user is manually escaping a name
            # Match on everything that follows the double-quote. Note that
            # text_len is calculated before removing the quote, so the
            # Completion.position value is correct
            text = text[1:]

        if mode == "fuzzy":
            fuzzy = True
            priority_func = self.prioritizer.name_count
        else:
            fuzzy = False
            priority_func = self.prioritizer.keyword_count

        # Construct a `_match` function for either fuzzy or non-fuzzy matching
        # The match function returns a 2-tuple used for sorting the matches,
        # or None if the item doesn't match
        # Note: higher priority values mean more important, so use negative
        # signs to flip the direction of the tuple
        if fuzzy:
            regex = ".*?".join(map(re.escape, text))
            pat = re.compile("(%s)" % regex)

            def _match(item):
                if item.lower()[: len(text) + 1] in (text, text + " "):
                    # Exact match of first word in suggestion
                    # This is to get exact alias matches to the top
                    # E.g. for input `e`, 'Entries E' should be on top
                    # (before e.g. `EndUsers EU`)
                    return float("Infinity"), -1
                r = pat.search(self.unescape_name(item.lower()))
                if r:
                    return -len(r.group()), -r.start()

        else:
            match_end_limit = len(text)

            def _match(item):
                match_point = item.lower().find(text, 0, match_end_limit)
                if match_point >= 0:
                    # Use negative infinity to force keywords to sort after all
                    # fuzzy matches
                    return -float("Infinity"), -match_point

        matches = []
        for cand in collection:
            if isinstance(cand, _Candidate):
                item, prio, display_meta, synonyms, prio2, display = cand
                if display_meta is None:
                    display_meta = meta
                syn_matches = (_match(x) for x in synonyms)
                # Nones need to be removed to avoid max() crashing in Python 3
                syn_matches = [m for m in syn_matches if m]
                sort_key = max(syn_matches) if syn_matches else None
            else:
                item, display_meta, prio, prio2, display = cand, meta, 0, 0, cand
                sort_key = _match(cand)

            if sort_key:
                if display_meta and len(display_meta) > 50:
                    # Truncate meta-text to 50 characters, if necessary
                    display_meta = display_meta[:47] + "..."

                # Lexical order of items in the collection, used for
                # tiebreaking items with the same match group length and start
                # position. Since we use *higher* priority to mean "more
                # important," we use -ord(c) to prioritize "aa" > "ab" and end
                # with 1 to prioritize shorter strings (ie "user" > "users").
                # We first do a case-insensitive sort and then a
                # case-sensitive one as a tie breaker.
                # We also use the unescape_name to make sure quoted names have
                # the same priority as unquoted names.
                lexical_priority = (
                    tuple(0 if c in " _" else -ord(c) for c in self.unescape_name(item.lower())) + (1,) + tuple(c for c in item)
                )

                item = self.case(item)
                display = self.case(display)
                priority = (
                    sort_key,
                    type_priority,
                    prio,
                    priority_func(item),
                    prio2,
                    lexical_priority,
                )
                matches.append(
                    Match(
                        completion=Completion(
                            text=item,
                            start_position=-text_len,
                            display_meta=display_meta,
                            display=display,
                        ),
                        priority=priority,
                    )
                )
        return matches

    def case(self, word):
        return self.casing.get(word, word)

    def get_completions(self, document, complete_event, smart_completion=None):
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        if smart_completion is None:
            smart_completion = self.smart_completion

        # If smart_completion is off then match any word that starts with
        # 'word_before_cursor'.
        if not smart_completion:
            matches = self.find_matches(word_before_cursor, self.all_completions, mode="strict")
            completions = [m.completion for m in matches]
            return sorted(completions, key=operator.attrgetter("text"))

        matches = []
        suggestions = suggest_type(document.text, document.text_before_cursor)

        for suggestion in suggestions:
            suggestion_type = type(suggestion)
            _logger.debug("Suggestion type: %r", suggestion_type)

            # Map suggestion type to method
            # e.g. 'table' -> self.get_table_matches
            matcher = self.suggestion_matchers[suggestion_type]
            matches.extend(matcher(self, suggestion, word_before_cursor))

        # Sort matches so highest priorities are first
        matches = sorted(matches, key=operator.attrgetter("priority"), reverse=True)

        return [m.completion for m in matches]


    def alias(self, tbl, tbls):
        """Generate a unique table alias
        tbl - name of the table to alias, quoted if it needs to be
        tbls - TableReference iterable of tables already in query
        """
        tbl = self.case(tbl)
        tbls = {normalize_ref(t.ref) for t in tbls}
        if self.generate_aliases:
            tbl = generate_alias(self.unescape_name(tbl), alias_map=self.alias_map)
        if normalize_ref(tbl) not in tbls:
            return tbl
        elif tbl[0] == '"':
            aliases = ('"' + tbl[1:-1] + str(i) + '"' for i in count(2))
        else:
            aliases = (tbl + str(i) for i in count(2))
        return next(a for a in aliases if normalize_ref(a) not in tbls)






    def _arg_list(self, func, usage):
        """Returns a an arg list string, e.g. `(_foo:=23)` for a func.

        :param func is a FunctionMetadata object
        :param usage is 'call', 'call_display' or 'signature'

        """
        pass


    def _make_cand(self, tbl, do_alias, suggestion, arg_mode=None):
        """Returns a Candidate namedtuple.

        :param tbl is a SchemaObject
        :param arg_mode determines what type of arg list to suffix for functions.
        Possible values: call, signature

        """
        pass











    suggestion_matchers = {
        FromClauseItem: get_from_clause_item_matches,
        JoinCondition: get_join_condition_matches,
        Join: get_join_matches,
        Column: get_column_matches,
        Function: get_function_matches,
        Schema: get_schema_matches,
        Table: get_table_matches,
        TableFormat: get_table_formats,
        View: get_view_matches,
        Alias: get_alias_matches,
        Database: get_database_matches,
        Keyword: get_keyword_matches,
        Special: get_special_matches,
        Datatype: get_datatype_matches,
        NamedQuery: get_namedquery_matches,
        Path: get_path_matches,
    }

    def populate_scoped_cols(self, scoped_tbls, local_tbls=()):
        """Find all columns in a set of scoped_tables.

        :param scoped_tbls: list of TableReference namedtuples
        :param local_tbls: tuple(TableMetadata)
        :return: {TableReference:{colname:ColumnMetaData}}

        """
        pass

    def _get_schemas(self, obj_typ, schema):
        """Returns a list of schemas from which to suggest objects.

        :param schema is the schema qualification input by the user (if any)

        """
        pass


    def populate_schema_objects(self, schema, obj_type):
        """Returns a list of SchemaObjects representing tables or views.

        :param schema is the schema qualification input by the user (if any)

        """
        pass

    def populate_functions(self, schema, filter_func):
        """Returns a list of function SchemaObjects.

        :param filter_func is a function that accepts a FunctionMetadata
        namedtuple and returns a boolean indicating whether that
        function should be kept or discarded

        """
        pass
