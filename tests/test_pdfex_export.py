from pathlib import Path

from acceptance_ext.config import bundled_tree_path, load_profile, load_tree
from acceptance_ext.exporters import export_pdfex
from acceptance_ext.extractors import DeterministicExtractor
from acceptance_ext.parsers.markdown import MarkdownParser


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic_standard.md"


def test_pdfex_shape():
    result = DeterministicExtractor().extract(MarkdownParser().parse(FIXTURE), load_profile())
    payload = export_pdfex(result, tree=load_tree(bundled_tree_path()))
    assert payload["tree"]
    root = payload["tree"][0]
    item_nodes = root["children"][0]["children"]
    assert item_nodes[0]["node_type"] == "分项"
    batch = item_nodes[0]["children"][0]
    assert batch["node_type"] == "检验批"
    assert batch["children"][0]["node_type"] == "验收项目"
    assert "verification_sources" in batch["children"][0]
