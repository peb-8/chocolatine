from typing import Iterable, List, Self

from typeguard import typechecked

from .having import Having
from .where import Where
from .select_from import SelectFrom
from .limit import Limit
from ..operator import Operator
from ..agg_function import AggFunction
from .named_expr import NamedExpr
from ..join_type import JoinType
from .condition import Condition
from .col import Col
from .table import Table


@typechecked
class Request(NamedExpr):
    """ Handler to generate a SQL request """
    def __init__(
            self,
            compact: bool = True,
            limit_to: int | None = None,
            using: bool = False,
            table: str | Table | None = None,
            unique: bool = False
    ) -> None:
        self._group_by_cols = []
        self._joins = []
        self._compact = compact
        self._last_joined_table = None
        self._joined_cols = {}
        self._using = using
        self._select_from = SelectFrom(table=table, unique=unique)
        self._limit = Limit(length=limit_to) if limit_to else None
        self._where = Where()
        self._having = Having()

    def table(self, val: str | Table | None) -> Self:
        """ Set the table name """
        self._select_from.from_expr.table = val
        return self

    def select(self, *vals: str | Col) -> Self:
        """ Set the selected cols """
        self._select_from.select.cols = vals
        return self

    def distinct(self) -> Self:
        """ Filter the rows to remove duplicates (by selected columns)"""
        self._select_from.select.unique = True
        return self

    def head(self, length: int = 1) -> Self:
        """ Filter on the first N rows """
        self._limit = length
        return self

    def filter(self, condition: Condition) -> Self:
        """ Filter the rows according to the given condition """
        if any(x in condition.build() for x in set(e.value for e in AggFunction)):
            self._having.condition = condition
        else:
            self._where.condition = condition
        return self

    def group_by(self, *cols_names: str) -> Self:
        """ Group the rows of the specified columns """
        self._group_by_cols = cols_names
        return self

    def join(self, table: str | Table, condition: Condition | str | Iterable[str], joinType: JoinType | None = JoinType.Inner) -> Self:
        """ Join two tables according to the given condition """
        if type(table) is str:
            table = Table(table)
        if not self._using:
            if not table._alias:
                table.alias()
            if not self._select_from.from_expr.table._alias:
                self._select_from.from_expr.table.alias()

            def _gen_condition(table, other, condition):
                left_table_alias = table._alias if type(table) is Table else Table(table)._alias
                right_table_alias = (other._alias if hasattr(other, "_alias") else None) or self._select_from.from_expr.table._alias
                self._joined_cols[condition] = (left_table_alias, right_table_alias)
                return Col(f"{left_table_alias}.{condition}") == Col(f"{right_table_alias}.{condition}")
            if type(condition) is not Condition:
                if type(condition) is str:
                    condition = _gen_condition(table, self._last_joined_table or self._select_from.from_expr.table, condition)
                else:
                    if len(condition) < 2:
                        raise ValueError("More conditions are expected")
                    for k in range(len(condition)):
                        if k == 0:
                            c = _gen_condition(table, self._select_from.from_expr.table, condition[0])
                        elif k > 0:
                            c = Condition(left_value=_gen_condition(table, self._select_from.from_expr.table, condition[k]), op=Operator.And, right_value=c)
                    condition = c
            self._joins.append((table if type(table) is Table else Table(table), joinType, condition))
        else:
            if type(condition) is Condition:
                raise ValueError("You cannot use a condition for joining two tables in when using mode is enabled")
            self._joins.append((table if type(table) is Table else Table(table), joinType, [condition] if type(condition) is str else condition))
        self._last_joined_table = table if type(table) is Table else Table(table)
        self._remove_select_cols_ambiguity()
        return self

    def _remove_select_cols_ambiguity(self) -> None:
        """ Correct the columns names in 'select' if they must be clarified with an alias """
        for selected_col in self._select_from.select.cols:
            if selected_col._name in self._joined_cols:
                selected_col._ref = self._joined_cols[selected_col._name][0]

    def _build_group_by(self) -> str:
        return f"GROUP BY {", ".join(self._group_by_cols)}" if self._group_by_cols else ""

    def _build_order_by(self) -> str:
        ordering = []
        for col in self._select_from.select.cols:
            if col._ordering is not None:
                ordering.append(f"{(col._ref + ".") if col._ref else ""}{col._alias if col._alias else col._name} {col._ordering.value}")
        return f"ORDER BY {", ".join(ordering)}" if ordering else ""

    def _build_join(self) -> List[str]:
        exprs = []
        for table, join_type, condition in self._joins:
            exprs.append(f"{join_type.value} JOIN {table}")
            if self._using:
                exprs.append(f"USING ({', '.join(condition)})")
            else:
                exprs.append(f"ON {condition}")
        return exprs

    def _build_limit(self) -> str:
        return f"LIMIT {self._limit}" if self._limit else ""

    def build(self) -> str:
        """ Build the query """
        return f"{" " if self._compact else "\n"}".join(
            part for part in [
                self._select_from.build(),
                *self._build_join(),
                self._where.build() if self._where.condition else "",
                self._build_group_by(),
                self._having.build() if self._having.condition else "",
                self._build_order_by(),
                self._limit.build() if self._limit else "",
            ] if part
        )
