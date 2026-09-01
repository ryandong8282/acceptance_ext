from __future__ import annotations

from .models import AuditFinding, ResultDocument


def validate(document: ResultDocument) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    seen: set[tuple[str | None, str]] = set()
    for division in document.tree:
        if not division.mapped_50300_path:
            findings.append(
                AuditFinding(
                    severity="warning",
                    code="ontology-unattached",
                    message=f"分项“{division.name}”未挂入 50300 本体",
                    node_id=division.id,
                )
            )
        for lot in division.children:
            if not lot.children:
                findings.append(
                    AuditFinding(
                        severity="warning",
                        code="empty-lot",
                        message=f"检验批“{lot.name}”没有验收项目",
                        node_id=lot.id,
                    )
                )
            for item in lot.children:
                key = (item.source_clause, item.name)
                if key in seen:
                    findings.append(
                        AuditFinding(
                            severity="warning",
                            code="duplicate-item",
                            message=f"重复验收项目：{item.source_clause} {item.name}",
                            node_id=item.id,
                        )
                    )
                seen.add(key)
                if not item.evidence or not item.source_quote:
                    findings.append(
                        AuditFinding(
                            severity="error",
                            code="missing-evidence",
                            message="验收项目缺少原文证据",
                            node_id=item.id,
                        )
                    )
                elif all(e.method == "inferred" for e in item.evidence):
                    findings.append(
                        AuditFinding(
                            severity="error",
                            code="inferred-only",
                            message="验收项目只有推断证据",
                            node_id=item.id,
                        )
                    )
    return findings


def metrics(document: ResultDocument, elapsed_seconds: float) -> dict[str, float | int]:
    divisions = len(document.tree)
    lots = sum(len(d.children) for d in document.tree)
    items = [item for d in document.tree for lot in d.children for item in lot.children]
    grounded = sum(bool(item.evidence and item.source_quote) for item in items)
    sampled = sum(item.min_sampling is not None for item in items)
    attached = sum(bool(d.mapped_50300_path) for d in document.tree)
    return {
        "division_count": divisions,
        "inspection_lot_count": lots,
        "acceptance_item_count": len(items),
        "grounding_rate": grounded / len(items) if items else 0.0,
        "sampling_coverage": sampled / len(items) if items else 0.0,
        "ontology_attachment_rate": attached / divisions if divisions else 0.0,
        "elapsed_seconds": round(elapsed_seconds, 4),
    }
