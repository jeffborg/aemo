from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from typing import Iterable


RecordKey = tuple[str, str]


def read_aemo_records(zip_bytes: bytes, wanted: Iterable[RecordKey]) -> dict[RecordKey, list[dict[str, str]]]:
    wanted_keys = set(wanted)
    headers: dict[RecordKey, list[str]] = {}
    rows: dict[RecordKey, list[dict[str, str]]] = defaultdict(list)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if not members:
            return {}

        with archive.open(members[0], "r") as handle:
            reader = csv.reader(io.TextIOWrapper(handle, encoding="utf-8", newline=""))
            for row in reader:
                if len(row) < 4:
                    continue
                record_type, dataset, table = row[0], row[1], row[2]
                key = (dataset, table)
                if record_type == "I":
                    headers[key] = row[4:]
                    continue
                if record_type != "D" or key not in wanted_keys:
                    continue
                fieldnames = headers.get(key)
                if not fieldnames:
                    continue
                values = row[4:]
                padded_values = values + [""] * max(0, len(fieldnames) - len(values))
                rows[key].append(dict(zip(fieldnames, padded_values)))

    return rows

