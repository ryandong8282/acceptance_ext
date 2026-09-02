# Acceptance Ext

中国建筑工程验收规范的可追溯结构化抽取实验。v0.2 的目标不再是“差不多像 PDFex”，而是直接输出 PDFex 当前使用的 `ResultDocument / ResultNode` 数据契约。

## v0.2 变化

- 新增 `semantic-v2`：按完整条文边界关联“检查数量 / 检验方法”，识别主控项目和一般项目，展开 HTML `rowspan/colspan` 表格。
- 抽样要求同时输出自然语言、受限 DSL、`min_sampling_json` 和证据对象。
- `--pdfex-output` 现在从真实 GB 50300 路径开始，保留原本体 ID、`type`、`type_name` 和 `node_type`。
- 新增 `compare-pdfex`，可以把 Acceptance Pi 与 Acceptance Ext 的同形 JSON 做条文级语义比较。
- 仓库内提交了 GB 50204-2015 第 4.2 节的人工语义金标、对齐结果与裁判报告。

## 运行

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

acceptance-ext extract \
  02_GB_50204-2015_混凝土结构工程施工质量验收规范.md \
  --parser markdown \
  --extractor semantic-v2 \
  --ontology /path/to/pdf_extractor/frontend/50300.json \
  --output output/native.json \
  --pdfex-output output/pdfex.json \
  --review-html output/review.html
```

对同一份文档的两个结果进行比较：

```bash
acceptance-ext compare-pdfex \
  /path/to/acceptance-pi-result.json \
  output/pdfex.json \
  --output output/head-to-head.json
```

复现本仓库的 4.2 节语义基准：

```bash
python scripts/benchmark_gb50204_ch4.py \
  /path/to/02_GB_50204-2015_混凝土结构工程施工质量验收规范.md
```

## 已冻结的局部基准

范围仅为 GB 50204-2015 第 4.2 节“模板安装”：42 个验收语义项，22 个抽样分支。结果见 [`reports/gb50204_ch4/SEMANTIC_REPORT.md`](reports/gb50204_ch4/SEMANTIC_REPORT.md)。这不是整本规范准确率，也不是 Acceptance Pi 的成绩；没有实际 Acceptance Pi 结果 JSON 时，不宣称胜过原项目。
