from __future__ import annotations

import re
from datetime import datetime


FIELD_PATTERN = re.compile(r"^(?P<key>[^:]+?)\s*:\s*(?P<value>.*)$")


def parse_market_notice(text: str, source_url: str) -> dict[str, str]:
    fields: dict[str, str] = {"source_url": source_url, "raw_text": text.strip()}
    reason_lines: list[str] = []
    in_reason = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_reason:
                reason_lines.append("")
            continue
        if line.startswith("END OF REPORT"):
            break
        if line.strip("-") == "":
            continue
        match = FIELD_PATTERN.match(line)
        if match and not in_reason:
            key = match.group("key").strip().lower().replace(" ", "_")
            value = match.group("value").strip()
            fields[key] = value
            in_reason = key == "reason"
            continue
        if in_reason:
            reason_lines.append(line)

    creation_date = fields.get("creation_date")
    if creation_date:
        fields["creation_datetime"] = datetime.strptime(creation_date, "%d/%m/%Y     %H:%M:%S").isoformat()

    issue_date = fields.get("issue_date")
    if issue_date:
        fields["issue_date"] = datetime.strptime(issue_date, "%d/%m/%Y").date().isoformat()

    fields["reason_text"] = "\n".join(reason_lines).strip()
    return fields

