import logging
import sqlite3
import datetime

from typing import Callable, Generic, List, TypeVar, Any, Tuple, get_args
from enum import Enum

from ._where import build_expression

T = TypeVar("T")

__all__ = [
    "stored_class",
    "StoredFiled",
    "select_field_names",
    "insert_field_names",
    "update_on_conflict_clause",
    "get_stored_attrs",
    "is_class_stored",
]

CLASS_STORED_ATTR = "__StoredFields__"
CLASS_TABLE_ATTR = "__StoreTable__"


class StoredAttr:
    name: str
    field: str
    insert: bool
    update: bool
    store_type: str
    to_db: Callable[[Any], Any]
    from_db: Callable[[Any], Any]

    def __init__(
        self,
        *,
        name: str,
        field: str,
        insert: bool,
        update: bool,
        store_type: str,
        not_null: bool,
        primary_key: bool,
        unique: bool,
        to_db: Callable[[Any], Any] = None,
        from_db: Callable[[Any], Any] = None,
    ) -> None:
        self.name = name
        self.field = field
        self.insert = insert
        self.update = update
        self.store_type = store_type
        self.not_null = not_null
        self.primary_key = primary_key
        self.unique = unique

        self.to_db = to_db
        self.from_db = from_db

        if self.to_db is None:
            self.to_db = lambda v: v
        if self.from_db is None:
            self.from_db = lambda v: v

    def __repr__(self) -> str:
        return f"{self.field} {self.store_type} insert: {self.insert} update: {self.update}"

    @property
    def update_excluded(self) -> str:
        return f"{self.field} = excluded.{self.field}"

    def definition(self) -> str:
        fld_def = f"{self.field} {self.store_type}"
        if self.not_null:
            fld_def += " not null"
        elif self.unique:
            fld_def += " unique"
        return fld_def


def get_stored_attrs(
    cls, filter: Callable[[StoredAttr], bool] = None
) -> List[StoredAttr]:
    if not hasattr(cls, CLASS_STORED_ATTR):
        return []
    attr: List[StoredAttr] = getattr(cls, CLASS_STORED_ATTR)
    if not filter:
        return attr
    return [x for x in attr if filter(x)]


def _get_select_field_names(cls, table_alias: str = None) -> List[str]:
    return [
        f"{table_alias and f'{table_alias}.' or ''}{x.field}"
        for x in get_stored_attrs(cls)
    ]


def _get_insert_field_names(cls, table_alias: str = None) -> List[str]:
    return [
        f"{table_alias and f'{table_alias}.' or ''}{x.field}"
        for x in get_stored_attrs(cls, lambda s: s.insert)
    ]


def _get_insert_placeholders(cls) -> str:
    return ", ".join(
        ["?"] * len([x for x in get_stored_attrs(cls, lambda s: s.insert)])
    )


def _get_update_on_conflict_clause(cls, conflict_fields: List[str] = []) -> str:
    return ",\n    ".join(
        [
            x.update_excluded
            for x in get_stored_attrs(
                cls, lambda s: s.insert and s.field not in conflict_fields
            )
        ]
    )


def _get_select_fields(self):
    attr = get_stored_attrs(self.__class__)
    return tuple([x.to_db(getattr(self, x.field)) for x in attr])


def _get_stored_field_tuple(self):
    attr = get_stored_attrs(self.__class__)
    return {x.name: x.to_db(getattr(self, x.name)) for x in attr}


def _get_insert_fields(self):
    attr = get_stored_attrs(self.__class__, lambda s: s.insert)
    return tuple([x.to_db(getattr(self, x.name)) for x in attr])


def _get_update_fields(self):
    attr = get_stored_attrs(self.__class__, lambda s: s.update)
    return tuple([x.to_db(getattr(self, x.name)) for x in attr])


def _update_from_db(self, **kwargs):
    attr = get_stored_attrs(self.__class__)
    for a in attr:
        setattr(self, a.name, a.from_db(kwargs[a.field]))


def add_class_method(cls, fn, name: str = None):
    name = name or fn.__name__
    if not hasattr(cls, name):
        setattr(cls, name, classmethod(fn))


def add_method(cls, fn, name: str = None):
    name = name or fn.__name__
    if not hasattr(cls, name):
        setattr(cls, name, fn)


STORED_TYPES = {
    str: "text",
    int: "integer",
    bool: "integer",
    float: "real",
    datetime.datetime: "text",
}


def stored_type(field_type: type) -> str:
    if field_type in STORED_TYPES:
        return STORED_TYPES[field_type]
    if issubclass(field_type, Enum):
        return "text"
    return field_type.__name__


class StoredField(Generic[T]):
    def __init__(
        self,
        field_name: str = None,
        store_as: type = None,
        insert: bool = True,
        update: bool = True,
        get: Callable[[Any], T] = None,
        set: Callable[[Any, T], None] = None,
        to_db: Callable[[T], Any] = None,
        from_db: Callable[[Any], T] = None,
        not_null: bool = False,
        primary_key: bool = False,
        unique: bool = False,
    ) -> None:
        super().__init__()
        self.name = field_name
        self.field_name = field_name
        self.store_as = store_as
        self.insert = insert
        self.update = update
        self.fget = get
        self.fset = set
        self.to_db = to_db
        self.from_db = from_db
        self.not_null = not_null
        self.primary_key = primary_key
        self.unique = unique

    def __set_name__(self, owner, name) -> None:
        field_type: type = get_args(self.__orig_class__)[0]
        store_type: type = stored_type(self.store_as or field_type)

        if field_type is datetime.datetime and self.to_db is None:
            self.to_db = lambda s: f"{s}"
        if field_type is datetime.datetime and self.from_db is None:
            self.from_db = lambda s: datetime.datetime.fromisoformat(s)
        if self.to_db is None and issubclass(field_type, Enum):
            self.to_db = lambda s: s.value
        if self.from_db is None and issubclass(field_type, Enum):
            # print(f"Make converter for {field_type}")
            self.from_db = lambda s: field_type(s)

        self.name = f"{name}_"
        if not hasattr(owner, CLASS_STORED_ATTR):
            setattr(owner, CLASS_STORED_ATTR, list[StoredAttr]())
        getattr(owner, CLASS_STORED_ATTR).append(
            StoredAttr(
                name=name,
                field=self.field_name or name,
                insert=self.insert,
                update=self.update,
                to_db=self.to_db,
                from_db=self.from_db,
                store_type=store_type,
                not_null=self.not_null,
                primary_key=self.primary_key,
                unique=self.unique,
            )
        )

        add_class_method(owner, _get_select_field_names)
        add_class_method(owner, _get_insert_field_names)
        add_class_method(owner, _get_insert_placeholders)
        add_class_method(owner, _get_update_on_conflict_clause)
        add_method(owner, _get_select_fields)
        add_method(owner, _get_insert_fields)
        add_method(owner, _get_update_fields)
        add_method(owner, _get_stored_field_tuple)
        add_method(owner, _update_from_db)

    def __get__(self, obj: Any, objtype=None) -> T:
        if self.fget:
            return self.fget(obj)
        if hasattr(obj, self.name):
            return getattr(obj, self.name)
        return None

    def __set__(self, obj: Any, val: T) -> None:
        if self.fset:
            self.fset(obj, val)
        elif not self.fget:  # Do not set if the property has a getter
            setattr(obj, self.name, val)


class PrimaryKey:
    def __init__(self, fields: List[StoredAttr]) -> None:
        self.attrs = fields

    def definition(self) -> str:
        return f"primary key ({', '.join([x.field for x in self.attrs])})"


def select_field_names(cls: type, table_alias: str = None) -> str:
    return ",\n       ".join(cls._get_select_field_names(table_alias))


def insert_field_names(cls: type, table_alias: str = None) -> str:
    return ", ".join(cls._get_insert_field_names(table_alias))


def insert_placeholders(cls: type) -> str:
    return cls._get_insert_placeholders()


def update_on_conflict_clause(cls: type, conflict_fields: List[str] = []) -> str:
    return cls._get_update_on_conflict_clause(conflict_fields)


def _make_log_function(
    logger_name: str, log_level: int, verbose: bool
) -> Callable[[Any], None]:
    if verbose:
        logger = logging.getLogger(logger_name)

        def _log_fn(msg, *args):
            logger.log(log_level, msg, *args)

        return _log_fn
    else:

        def _dont_log(msg, *args):
            pass

        return _dont_log


def _make_ddl_fn(
    cls: type,
    table_name: str,
    log_run: Callable[[str, Tuple[Any]], None],
    log_create: Callable[[str, Tuple[Any]], None],
) -> Any:
    attrs = get_stored_attrs(cls)
    if not attrs:
        return None
    pkeys = [x for x in attrs if x.primary_key]
    key_count = len(pkeys)
    constraints = []
    if pkeys:
        constraints.append(PrimaryKey(pkeys))

    field_sep = ",\n    "
    ddl_query = f"""
create table if not exists {table_name} (
    {field_sep.join([x.definition() for x in attrs + constraints])}
)
"""
    log_create(f"Create table query: {ddl_query}")

    def _ddl_fn(cls) -> str:
        return ddl_query

    return _ddl_fn


def _make_drop_ddl_fn(
    cls: type,
    table_name: str,
    log_run: Callable[[str, Tuple[Any]], None],
    log_create: Callable[[str, Tuple[Any]], None],
) -> Any:
    if not hasattr(cls, CLASS_STORED_ATTR):
        return None

    def _drop_ddl(cls) -> str():
        log_run(f"Dropping table {table_name}")
        return f"drop table if exists {table_name}"

    return _drop_ddl


def _make_select_fn(
    cls: type,
    table_name: str,
    log_run: Callable[[str, Tuple[Any]], None],
    log_create: Callable[[str, Tuple[Any]], None],
) -> Any:
    select_query = f"""
select {select_field_names(cls)}
from {table_name}
"""

    log_create(f"Select query {select_query}")
    attrs = get_stored_attrs(cls)
    attr_names = [x.field for x in attrs]
    attr_map = {x.name: x for x in attrs}
    attr_set = {x.name for x in attrs}

    def _make_object(*args):
        o = cls.__new__(cls)
        super(cls, o).__init__()
        data = {k: v for k, v in zip(attr_names, args)}
        o._update_from_db(**data)
        return o

    has_on_load = hasattr(cls, "on_load")

    def _select_fn(
        cls: type, conn: sqlite3.Connection, *args, order: List[str] = None, **kwargs
    ) -> List[cls]:
        # TODO order
        cursor = None
        if args or kwargs:
            # TODO more comlicated where
            args_names = [x for x, _ in kwargs.items()]
            missing = set(args_names) - attr_set
            if missing:
                raise KeyError(
                    f"{cls.__name__} doesn't have {missing} fields in database"
                )
            where = build_expression(*args, **kwargs)
            where_clause = " where " + where.expression
            cursor = conn.execute(select_query + where_clause, where.params)
        else:
            cursor = conn.execute(select_query)
        objs = [_make_object(*row) for row in cursor]
        if has_on_load:
            for o in objs:
                o.on_load(conn, *args)
        return objs

    return _select_fn


def _make_store_fn(
    cls: type,
    table_name: str,
    id_fields: List[str],
    log_run: Callable[[str, Tuple[Any]], None],
    log_create: Callable[[str, Tuple[Any]], None],
) -> None:
    store_query = f"""
insert into {table_name}({insert_field_names(cls)})
values ({insert_placeholders(cls)})
on conflict({", ".join(id_fields)})
do update
set {update_on_conflict_clause(cls, id_fields)}
"""
    log_create(f"Store query {store_query}")

    has_on_store = hasattr(cls, "on_store")

    def _store_fn(self, conn: sqlite3.Connection) -> None:
        log_run(f"Store {self}")
        conn.execute(store_query, self._get_insert_fields())
        if has_on_store:
            self.on_store(conn)
        # commit?

    return _store_fn


def _build_db_class(
    cls: type,
    table_name: str,
    id_fields: List[str],
    store_fn_name: str,
    load_fn_name: str,
    log_level: int,
    verbose: bool,
) -> type:
    log_create = _make_log_function(
        f"{cls.__name__}_DB", log_level=log_level, verbose=verbose
    )
    log_run = _make_log_function(
        f"{cls.__name__}_DB", log_level=log_level, verbose=True
    )
    setattr(cls, CLASS_TABLE_ATTR, table_name)

    log_create(f"Start build DB functions")

    ddl_fn = _make_ddl_fn(cls, table_name, log_run, log_create)
    add_class_method(cls, ddl_fn, "_create_ddl")

    drop_fn = _make_drop_ddl_fn(cls, table_name, log_run, log_create)
    add_class_method(cls, drop_fn, "_drop_ddl")

    select_fn = _make_select_fn(cls, table_name, log_run, log_create)
    add_class_method(cls, select_fn, load_fn_name)

    store_fn = _make_store_fn(cls, table_name, id_fields, log_run, log_create)
    add_method(cls, store_fn, store_fn_name)

    return cls


def stored_class(
    _=None,
    *,
    table_name: str,
    id_fields: List[str],
    store_fn_name="_store_to_db",
    load_fn_name: str = "_load_from_db",
    log_level: int = logging.INFO,
    verbose: bool = False,
) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        return _build_db_class(
            cls,
            table_name=table_name,
            id_fields=id_fields,
            store_fn_name=store_fn_name,
            load_fn_name=load_fn_name,
            log_level=log_level,
            verbose=verbose,
        )

    return decorator


def is_class_stored(cls):
    return hasattr(cls, CLASS_STORED_ATTR)
