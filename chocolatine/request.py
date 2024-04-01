from typing import Self
from chocolatine.expr import Expr
from chocolatine.join_type import JoinType
from .condition import Condition
from .col import Col
from .table import Table


class Request(Expr):

    def __init__(
            self,
            compact: bool = True
    ):
        self._table = None
        self.selected_cols = []
        self.unique = False
        self.group_by_cols = []
        self.where_condition = []
        self.having_condition = []
        self.joins = []
        self.compact = compact

    def table(self, table_name: str, table_new_name: str = None) -> Self:
        self._table = Table(table_name, table_new_name)
        return self

    def select(self, *selected_cols) -> Self:
        self.selected_cols = selected_cols
        return self

    def distinct(self) -> Self:
        self.unique = True
        return self

    def filter(self, where_condition: Condition = None, having_condition: Condition = None) -> Self:
        if where_condition is None and having_condition is None:
            raise Exception("At least one of where or having condition must be specified")
        self.where_condition = where_condition
        self.having_condition = having_condition
        return self

    def group_by(self, *cols) -> Self:
        self.group_by_cols = cols
        return self

    def join(self, table: str, joinType: JoinType, condition: Condition) -> Self:
        self.joins.append((table, joinType, condition))
        return self

    def build_select(self) -> str:
        expr = "SELECT "
        if self.selected_cols:
            cols = ", ".join([str(col) for col in self.selected_cols])
        else:
            cols = "*"
        if self.unique:
            expr += f"DISTINCT({cols})"
        else:
            expr += cols
        return expr

    def build_from(self) -> str:
        return f"FROM {self._table}"

    def build_where(self) -> str:
        if self.where_condition:
            return f"WHERE {self.where_condition}"
        return ""

    def build_group_by(self) -> str:
        if self.group_by_cols:
            return f"GROUP BY {", ".join(self.group_by_cols)}"
        return ""

    def build_having(self) -> str:
        if self.having_condition:
            return f"HAVING {self.having_condition}"
        return ""

    def build_order_by(self) -> str:
        ordering = []
        for col in self.selected_cols:
            if type(col) is Col and col.ordering is not None:
                ordering.append(f"{col.name} {col.ordering.value}")
        if ordering:
            return f"ORDER BY {", ".join(ordering)}"
        return ""

    def build_join(self) -> str:
        exprs = []
        for table, join_type, condition in self.joins:
            exprs.append(f"{join_type.value} JOIN {table}")
            exprs.append(f"ON {condition}")
        return exprs

    def build(self) -> str:
        return f"{" " if self.compact else "\n"}".join(
            part for part in [
                self.build_select(),
                self.build_from(),
                self.build_where(),
                *self.build_join(),
                self.build_group_by(),
                self.build_having(),
                self.build_order_by()
            ] if part
        )
