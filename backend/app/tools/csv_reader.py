
"""Controlled operations over checksum-verified, registered CSV datasets."""

from __future__ import annotations

import asyncio
import hashlib
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ToolExecutionError, ToolInputError
from app.repositories.documents import DatasetRepository
from app.tools.base import BaseTool
from app.tools.schemas import CSVReaderInput, CSVReaderOutput

MAX_ROWS_RETURNED = 200


class CSVReaderTool(BaseTool[CSVReaderInput, CSVReaderOutput]):
    """Read and analyze registered CSV files inside the configured data root."""

    name = "csv_reader"
    description = (
        "Describe, preview, filter, aggregate, or rank rows in registered local CSV datasets."
    )
    input_model = CSVReaderInput
    output_model = CSVReaderOutput
    timeout = 30.0

    def __init__(
        self,
        session: AsyncSession | None = None,
        data_root: Path | None = None,
        timeout: float | None = None,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        self.data_root = (data_root or settings.data_root).resolve()

        if timeout is not None:
            self.timeout = timeout

    async def run(self, input: CSVReaderInput) -> CSVReaderOutput:
        """Execute an operation on a registered, checksum-matched CSV."""
        if self.session is None and self.session_factory is None:
            raise ToolExecutionError(
                "CSV reading requires an async database session or session factory"
            )

        csv_root = (self.data_root / "csv").resolve()
        target = (csv_root / input.filename).resolve()

        try:
            target.relative_to(csv_root)
        except ValueError as exc:
            raise ToolInputError(
                "CSV filename must resolve inside the configured csv directory"
            ) from exc

        if not target.is_file():
            raise ToolInputError(
                "CSV file does not exist in the configured csv directory: "
                f"{input.filename}"
            )

        # Open a short-lived session when a session factory is available.
        if self.session_factory is not None:
            async with self.session_factory() as session:
                dataset = await DatasetRepository(session).get_by_filename(
                    input.filename
                )
                if dataset is None:
                    raise ToolInputError(
                        f"CSV file is not registered as a dataset: {input.filename}"
                    )

                # Copy the needed database value before closing the session.
                registered_checksum = dataset.checksum
                registered_filename = dataset.filename
        else:
            dataset = await DatasetRepository(self.session).get_by_filename(
                input.filename
            )
            if dataset is None:
                raise ToolInputError(
                    f"CSV file is not registered as a dataset: {input.filename}"
                )

            registered_checksum = dataset.checksum
            registered_filename = dataset.filename

        raw_content = await asyncio.to_thread(target.read_bytes)
        checksum = hashlib.sha256(raw_content).hexdigest()

        if checksum != registered_checksum:
            raise ToolExecutionError(
                "Registered CSV checksum no longer matches on-disk file: "
                f"{input.filename}"
            )

        frame = await asyncio.to_thread(
            pd.read_csv,
            io.BytesIO(raw_content),
        )
        working = frame.copy()
        filters_applied: list[dict[str, Any]] = []

        if input.operation == "describe":
            result: Any = {
                "schema": [
                    {"name": str(column), "dtype": str(dtype)}
                    for column, dtype in frame.dtypes.items()
                ],
                "row_count": len(frame.index),
                "null_counts": {
                    str(column): int(count)
                    for column, count in frame.isna().sum().items()
                },
            }

        elif input.operation == "head":
            result = self._records(
                working.head(min(input.n, MAX_ROWS_RETURNED))
            )

        elif input.operation == "filter":
            if input.column is None or input.operator is None:
                raise ToolInputError(
                    "filter requires both column and operator"
                )

            self._require_column(frame, input.column)
            working = self._apply_filter(working, input)

            filters_applied.append(
                {
                    "column": input.column,
                    "operator": input.operator,
                    "value": input.value,
                }
            )

            result = self._records(working.head(MAX_ROWS_RETURNED))

        elif input.operation == "aggregate":
            for column in input.group_by:
                self._require_column(frame, column)

            if input.metric_column is not None:
                self._require_column(frame, input.metric_column)

            result = self._aggregate(working, input)[:MAX_ROWS_RETURNED]

        else:
            if input.operation != "top_n" or input.column is None:
                raise ToolInputError("top_n requires a column")

            self._require_column(frame, input.column)

            ordered = working.sort_values(
                by=input.column,
                ascending=input.ascending,
                na_position="last",
            )

            result = self._records(
                ordered.head(min(input.n, MAX_ROWS_RETURNED))
            )

        return CSVReaderOutput(
            operation=input.operation,
            result=result,
            provenance={
                "dataset": registered_filename,
                "row_count_scanned": len(frame.index),
                "filters_applied": filters_applied,
            },
        )

    @staticmethod
    def _require_column(frame: pd.DataFrame, column: str) -> None:
        """Raise a typed input error when a column is absent."""
        if column not in frame.columns:
            raise ToolInputError(f"Unknown CSV column: {column}")

    @classmethod
    def _apply_filter(
        cls,
        frame: pd.DataFrame,
        input: CSVReaderInput,
    ) -> pd.DataFrame:
        """Apply one explicitly selected dataframe predicate."""
        column = input.column
        operator_name = input.operator

        if column is None or operator_name is None:
            raise ToolInputError(
                "filter requires both column and operator"
            )

        try:
            series = frame[column]
            value = input.value

            if operator_name == "eq":
                mask = series == value
            elif operator_name == "ne":
                mask = series != value
            elif operator_name == "gt":
                mask = series > value
            elif operator_name == "lt":
                mask = series < value
            elif operator_name == "gte":
                mask = series >= value
            elif operator_name == "lte":
                mask = series <= value
            elif operator_name == "in":
                mask = series.isin(value)
            else:
                if not isinstance(value, str):
                    raise ToolInputError(
                        "contains filter value must be a string"
                    )

                mask = series.astype("string").str.contains(
                    value,
                    case=False,
                    regex=False,
                    na=False,
                )

            return frame.loc[mask]

        except ToolInputError:
            raise
        except (TypeError, ValueError) as exc:
            raise ToolInputError(
                f"Invalid value for filter on column {column}: {exc}"
            ) from exc

    @classmethod
    def _aggregate(
        cls,
        frame: pd.DataFrame,
        input: CSVReaderInput,
    ) -> list[dict[str, Any]]:
        """Compute an optional grouped aggregation with JSON-safe values."""
        agg = input.agg
        metric_column = input.metric_column

        if agg is None:
            raise ToolInputError(
                "aggregate requires an aggregation function"
            )

        if agg == "count" and metric_column is None:
            if input.group_by:
                grouped = (
                    frame.groupby(input.group_by, dropna=False)
                    .size()
                    .reset_index(name="count")
                )
            else:
                grouped = pd.DataFrame(
                    [{"count": len(frame.index)}]
                )

            return cls._records(grouped)

        if metric_column is None:
            raise ToolInputError(
                f"aggregate {agg} requires metric_column"
            )

        try:
            if input.group_by:
                grouped_data = frame.groupby(
                    input.group_by,
                    dropna=False,
                )[metric_column]

                aggregate = getattr(grouped_data, agg)()
                grouped = aggregate.reset_index(name=agg)
            else:
                value = getattr(frame[metric_column], agg)()
                grouped = pd.DataFrame([{agg: value}])

        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise ToolInputError(
                f"Cannot apply {agg} to column {metric_column}: {exc}"
            ) from exc

        return cls._records(grouped)

    @staticmethod
    def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        """Convert a bounded dataframe view to JSON-compatible records."""
        safe_frame = frame.astype(object).where(
            pd.notna(frame),
            None,
        )

        records: list[dict[str, Any]] = []

        for record in safe_frame.to_dict(orient="records"):
            clean_record: dict[str, Any] = {}

            for key, value in record.items():
                if hasattr(value, "item"):
                    value = value.item()

                clean_record[str(key)] = value

            records.append(clean_record)

        return records




# """Controlled operations over checksum-verified, registered CSV datasets."""

# from __future__ import annotations

# import asyncio
# import hashlib
# import io
# from pathlib import Path
# from typing import Any
# from collections.abc import Callable
# import pandas as pd
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import settings
# from app.core.errors import ToolExecutionError, ToolInputError
# from app.repositories.documents import DatasetRepository
# from app.tools.base import BaseTool
# from app.tools.schemas import CSVReaderInput, CSVReaderOutput

# MAX_ROWS_RETURNED = 200


# class CSVReaderTool(BaseTool[CSVReaderInput, CSVReaderOutput]):
#     """Read and analyze registered CSV files inside the configured data root."""

#     name = "csv_reader"
#     description = (
#         "Describe, preview, filter, aggregate, or rank rows in registered local CSV datasets."
#     )
#     input_model = CSVReaderInput
#     output_model = CSVReaderOutput
#     timeout = 30.0

#     def __init__(
#         self,
#         session: AsyncSession | None = None,
#         data_root: Path | None = None,
#         timeout: float | None = None,
#     ) -> None:
#         self.session = session
#         self.data_root = (data_root or settings.data_root).resolve()
#         if timeout is not None:
#             self.timeout = timeout

#     async def run(self, input: CSVReaderInput) -> CSVReaderOutput:
#         """Execute the requested operation on a registered checksum-matched CSV."""
#         if self.session is None:
#             raise ToolExecutionError("CSV reading requires an async database session")

#         csv_root = (self.data_root / "csv").resolve()
#         target = (csv_root / input.filename).resolve()
#         try:
#             target.relative_to(csv_root)
#         except ValueError as exc:
#             raise ToolInputError(
#                 "CSV filename must resolve inside the configured csv directory"
#             ) from exc
#         if not target.is_file():
#             raise ToolInputError(
#                 f"CSV file does not exist in the configured csv directory: {input.filename}"
#             )

#         dataset = await DatasetRepository(self.session).get_by_filename(input.filename)
#         if dataset is None:
#             raise ToolInputError(f"CSV file is not registered as a dataset: {input.filename}")

#         raw_content = await asyncio.to_thread(target.read_bytes)
#         checksum = hashlib.sha256(raw_content).hexdigest()
#         if checksum != dataset.checksum:
#             raise ToolExecutionError(
#                 f"Registered CSV checksum no longer matches on-disk file: {input.filename}"
#             )
#         frame = await asyncio.to_thread(pd.read_csv, io.BytesIO(raw_content))
#         working = frame.copy()
#         filters_applied: list[dict[str, Any]] = []

#         if input.operation == "describe":
#             result: Any = {
#                 "schema": [
#                     {"name": str(column), "dtype": str(dtype)}
#                     for column, dtype in frame.dtypes.items()
#                 ],
#                 "row_count": len(frame.index),
#                 "null_counts": {
#                     str(column): int(count) for column, count in frame.isna().sum().items()
#                 },
#             }
#         elif input.operation == "head":
#             result = self._records(working.head(min(input.n, MAX_ROWS_RETURNED)))
#         elif input.operation == "filter":
#             if input.column is None or input.operator is None:
#                 raise ToolInputError("filter requires both column and operator")
#             self._require_column(frame, input.column)
#             working = self._apply_filter(working, input)
#             filters_applied.append(
#                 {
#                     "column": input.column,
#                     "operator": input.operator,
#                     "value": input.value,
#                 }
#             )
#             result = self._records(working.head(MAX_ROWS_RETURNED))
#         elif input.operation == "aggregate":
#             for column in input.group_by:
#                 self._require_column(frame, column)
#             if input.metric_column is not None:
#                 self._require_column(frame, input.metric_column)
#             result = self._aggregate(working, input)[:MAX_ROWS_RETURNED]
#         else:
#             if input.operation != "top_n" or input.column is None:
#                 raise ToolInputError("top_n requires a column")
#             self._require_column(frame, input.column)
#             ordered = working.sort_values(
#                 by=input.column,
#                 ascending=input.ascending,
#                 na_position="last",
#             )
#             result = self._records(ordered.head(min(input.n, MAX_ROWS_RETURNED)))

#         return CSVReaderOutput(
#             operation=input.operation,
#             result=result,
#             provenance={
#                 "dataset": dataset.filename,
#                 "row_count_scanned": len(frame.index),
#                 "filters_applied": filters_applied,
#             },
#         )

#     @staticmethod
#     def _require_column(frame: pd.DataFrame, column: str) -> None:
#         """Raise a typed input error when a column is absent."""
#         if column not in frame.columns:
#             raise ToolInputError(f"Unknown CSV column: {column}")

#     @classmethod
#     def _apply_filter(cls, frame: pd.DataFrame, input: CSVReaderInput) -> pd.DataFrame:
#         """Apply one explicitly selected dataframe predicate."""
#         column = input.column
#         operator_name = input.operator
#         if column is None or operator_name is None:
#             raise ToolInputError("filter requires both column and operator")

#         try:
#             series = frame[column]
#             value = input.value
#             if operator_name == "eq":
#                 mask = series == value
#             elif operator_name == "ne":
#                 mask = series != value
#             elif operator_name == "gt":
#                 mask = series > value
#             elif operator_name == "lt":
#                 mask = series < value
#             elif operator_name == "gte":
#                 mask = series >= value
#             elif operator_name == "lte":
#                 mask = series <= value
#             elif operator_name == "in":
#                 mask = series.isin(value)
#             else:
#                 if not isinstance(value, str):
#                     raise ToolInputError("contains filter value must be a string")
#                 mask = series.astype("string").str.contains(
#                     value, case=False, regex=False, na=False
#                 )
#             return frame.loc[mask]
#         except ToolInputError:
#             raise
#         except (TypeError, ValueError) as exc:
#             raise ToolInputError(f"Invalid value for filter on column {column}: {exc}") from exc

#     @classmethod
#     def _aggregate(cls, frame: pd.DataFrame, input: CSVReaderInput) -> list[dict[str, Any]]:
#         """Compute an optional grouped aggregation with JSON-safe values."""
#         agg = input.agg
#         metric_column = input.metric_column
#         if agg is None:
#             raise ToolInputError("aggregate requires an aggregation function")

#         if agg == "count" and metric_column is None:
#             if input.group_by:
#                 grouped = (
#                     frame.groupby(input.group_by, dropna=False).size().reset_index(name="count")
#                 )
#             else:
#                 grouped = pd.DataFrame([{"count": len(frame.index)}])
#             return cls._records(grouped)
#         if metric_column is None:
#             raise ToolInputError(f"aggregate {agg} requires metric_column")

#         try:
#             if input.group_by:
#                 grouped_data = frame.groupby(input.group_by, dropna=False)[metric_column]
#                 aggregate = getattr(grouped_data, agg)()
#                 grouped = aggregate.reset_index(name=agg)
#             else:
#                 value = getattr(frame[metric_column], agg)()
#                 grouped = pd.DataFrame([{agg: value}])
#         except (TypeError, ValueError) as exc:
#             raise ToolInputError(f"Cannot apply {agg} to column {metric_column}: {exc}") from exc
#         return cls._records(grouped)

#     @staticmethod
#     def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
#         """Convert a bounded dataframe view to JSON-compatible records."""
#         safe_frame = frame.astype(object).where(pd.notna(frame), None)
#         records: list[dict[str, Any]] = []
#         for record in safe_frame.to_dict(orient="records"):
#             clean_record: dict[str, Any] = {}
#             for key, value in record.items():
#                 if hasattr(value, "item"):
#                     value = value.item()
#                 clean_record[str(key)] = value
#             records.append(clean_record)
#         return records
