# PDFex contract alignment v0.2

`acceptance-ext extract --pdfex-output` 的输出根字段为：

```text
source_pdf
standard_no
standard_name
extraction
chapters
tree
page_count
markdown_file
```

`tree` 从 GB 50300 原节点开始，而不是从一个自造的“分项工程”根开始。例如 GB 50204 模板安装：

```text
主体结构(id=2, type=3, type_name=分部, node_type=单位)
└── 混凝土结构(id=18, type=2, type_name=子分部)
    └── 模板(id=161, type=1, type_name=分项)
        └── 模板安装检验批
            └── 验收项目
```

验收项目保留 PDFex 字段：`source_clause`、`source_quote`、`item_category`、`check_method`、`table_no`、`deviation_unit`、`deviation_value`、`min_sampling`、`min_sampling_reason`、`min_sampling_confidence`、`min_sampling_script`、`min_sampling_json`、`min_sampling_rule`、`params`、`verification_sources`。

传入完整的 `frontend/50300.json` 时使用其中真实 ID；内置 seed 只用于模板、钢筋、混凝土、预应力、现浇结构、装配式结构和木结构的冒烟验证。
