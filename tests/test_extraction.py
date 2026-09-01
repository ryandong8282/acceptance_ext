from pathlib import Path

from acceptance_ext.config import load_profile
from acceptance_ext.extractors import DeterministicExtractor
from acceptance_ext.parsers.markdown import MarkdownParser


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic_standard.md"


def test_synthetic_extraction():
    ir = MarkdownParser().parse(FIXTURE)
    result = DeterministicExtractor().extract(ir, load_profile())
    result.refresh_stats()

    assert result.standard_no == "GB 90000-2099"
    assert result.stats.work_item_count == 1
    assert result.stats.batch_count == 1
    assert result.stats.acceptance_item_count == 4
    assert result.stats.table_row_item_count == 2

    items = [item for _, _, item in result.iter_items()]
    assert items[0].clause_no == "4.2.1"
    assert items[0].category == "主控项目"
    assert items[0].inspection_quantity == "全数检查。"
    assert items[1].sampling is not None
    assert len(items[1].sampling.branches) == 2
    assert {item.name for item in items[2:]} == {"轴线位置", "表面平整度"}


def test_standard_title_ignores_release_notice(tmp_path):
    source = tmp_path / "notice.md"
    source.write_text(
        "# 建筑给水排水及采暖工程施工质量验收规范 [PDF p.1]\n\n"
        "GB 50242—2002\n\n"
        "# 关于发布国家标准《建筑给水排水及采暖工程施工质量验收规范》的通知 [PDF p.2]\n\n"
        "# 4 室内给水系统安装 [PDF p.16]\n\n"
        "## 4.2 给水管道及配件安装 [PDF p.16]\n\n"
        "### 4.2.1 给水管道系统应进行水压试验。 [PDF p.16]\n\n"
        "检查数量：全数检查。\n\n"
        "检验方法：观察检查。\n",
        encoding="utf-8",
    )
    result = DeterministicExtractor().extract(MarkdownParser().parse(source), load_profile())
    assert result.standard_name == "建筑给水排水及采暖工程施工质量验收规范"
