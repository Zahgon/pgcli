from collections import namedtuple

_ColumnMetadata = namedtuple("ColumnMetadata", ["name", "datatype", "foreignkeys", "default", "has_default"])


def ColumnMetadata(name, datatype, foreignkeys=None, default=None, has_default=False):
    return _ColumnMetadata(name, datatype, foreignkeys or [], default, has_default)


ForeignKey = namedtuple(
    "ForeignKey",
    [
        "parentschema",
        "parenttable",
        "parentcolumn",
        "childschema",
        "childtable",
        "childcolumn",
    ],
)
TableMetadata = namedtuple("TableMetadata", "name columns")


def parse_defaults(defaults_string):
    """Yields default values for a function, given the string provided by
    pg_get_expr(pg_catalog.pg_proc.proargdefaults, 0)"""
    pass


class FunctionMetadata:
    def __init__(
        self,
        schema_name,
        func_name,
        arg_names,
        arg_types,
        arg_modes,
        return_type,
        is_aggregate,
        is_window,
        is_set_returning,
        is_extension,
        arg_defaults,
    ):
        """Class for describing a postgresql function"""

        self.schema_name = schema_name
        self.func_name = func_name

        self.arg_modes = tuple(arg_modes) if arg_modes else None
        self.arg_names = tuple(arg_names) if arg_names else None

        # Be flexible in not requiring arg_types -- use None as a placeholder
        # for each arg. (Used for compatibility with old versions of postgresql
        # where such info is hard to get.
        if arg_types:
            self.arg_types = tuple(arg_types)
        elif arg_modes:
            self.arg_types = tuple([None] * len(arg_modes))
        elif arg_names:
            self.arg_types = tuple([None] * len(arg_names))
        else:
            self.arg_types = None

        self.arg_defaults = tuple(parse_defaults(arg_defaults))

        self.return_type = return_type.strip()
        self.is_aggregate = is_aggregate
        self.is_window = is_window
        self.is_set_returning = is_set_returning
        self.is_extension = bool(is_extension)
        self.is_public = self.schema_name and self.schema_name == "public"

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)


    def __hash__(self):
        return hash(self._signature())

    def __repr__(self):
        return (
            "%s(schema_name=%r, func_name=%r, arg_names=%r, "
            "arg_types=%r, arg_modes=%r, return_type=%r, is_aggregate=%r, "
            "is_window=%r, is_set_returning=%r, is_extension=%r, arg_defaults=%r)"
        ) % ((self.__class__.__name__,) + self._signature())


    def args(self):
        """Returns a list of input-parameter ColumnMetadata namedtuples."""
        pass

    def fields(self):
        """Returns a list of output-field ColumnMetadata namedtuples"""
        pass
