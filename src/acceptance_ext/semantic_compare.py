from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _compact(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"[\s，。；：、（）()【】\[\]《》<>·—－_\-]+", "", str(value)).lower()


def flatten_pdfex(document: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    def walk(nodes: list[dict[str, Any]], path: list[str]) -> None:
        for node in nodes:
            current=[*path,str(node.get("name", ""))]
            if node.get("node_type") == "验收项目" or node.get("type_name") == "验收项目":
                rows.append({**node,"tree_path":current})
            children=node.get("children") or []
            if isinstance(children,list): walk(children,current)
    walk(document.get("tree") or [],[])
    return rows


def _name_score(a: str, b: str) -> float:
    a,b=_compact(a),_compact(b)
    if not a or not b: return 0.0
    if a==b or a in b or b in a: return 1.0
    aa={a[i:i+2] for i in range(max(1,len(a)-1))}; bb={b[i:i+2] for i in range(max(1,len(b)-1))}
    return 2*len(aa&bb)/max(1,len(aa)+len(bb))


def compare_pdfex_documents(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    expected=flatten_pdfex(baseline); predicted=flatten_pdfex(candidate); used:set[int]=set(); pairs=[]; missing=[]
    for left in expected:
        best_i=None;best=0.0
        for i,right in enumerate(predicted):
            if i in used or left.get("source_clause")!=right.get("source_clause"): continue
            score=_name_score(left.get("name",""),right.get("name",""))
            if score>best: best_i,best=i,score
        if best_i is None or best<0.72: missing.append(left); continue
        used.add(best_i); pairs.append((left,predicted[best_i]))
    extra=[x for i,x in enumerate(predicted) if i not in used]
    tp=len(pairs); precision=tp/len(predicted) if predicted else 0.0; recall=tp/len(expected) if expected else 0.0
    fields=["item_category","check_method","min_sampling","min_sampling_script","params","deviation_value","table_no"]
    field_accuracy={field:(sum(_compact(a.get(field))==_compact(b.get(field)) for a,b in pairs)/tp if tp else 0.0) for field in fields}
    path_accuracy=sum([_compact(a.get("tree_path")[:3])==_compact(b.get("tree_path")[:3]) for a,b in pairs])/tp if tp else 0.0
    evidence_accuracy=sum(bool(b.get("source_quote") and b.get("verification_sources")) for _,b in pairs)/tp if tp else 0.0
    return {
        "baseline_item_count":len(expected),"candidate_item_count":len(predicted),"matched_item_count":tp,
        "item_precision":round(precision,4),"item_recall":round(recall,4),
        "item_f1":round(2*precision*recall/(precision+recall),4) if precision+recall else 0.0,
        "field_accuracy":{k:round(v,4) for k,v in field_accuracy.items()},
        "ontology_path_accuracy":round(path_accuracy,4),"candidate_grounding_rate":round(evidence_accuracy,4),
        "missing":[{"source_clause":x.get("source_clause"),"name":x.get("name"),"tree_path":x.get("tree_path")} for x in missing],
        "extra":[{"source_clause":x.get("source_clause"),"name":x.get("name"),"tree_path":x.get("tree_path")} for x in extra],
    }


def compare_pdfex_files(baseline_path: Path, candidate_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    result=compare_pdfex_documents(json.loads(baseline_path.read_text(encoding="utf-8-sig")),json.loads(candidate_path.read_text(encoding="utf-8-sig")))
    if output_path:
        output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
