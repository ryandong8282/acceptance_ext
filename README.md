# Acceptance Ext

面向中国工程建设验收规范的 **可追溯结构化抽取实验台**。项目把不同 PDF/Markdown 解析器、确定性基线和 OpenAI-compatible 复核器放到同一条可评测流水线中，输出统一的“分项 → 检验批 → 验收项目”结构，并保存原文证据、审计结果与指标。

## Web Workbench

仓库内置一套不需要 Node 构建的本地 Web 界面，复用了 PDFex 的核心交互方式：

- **抽取工作台**：上传 PDF/Markdown、选择 parser/extractor、查看结构树、字段详情、原文证据和 JSON；
- **Job 运行控制台**：后台队列、状态筛选、取消、重跑、删除；
- **执行时间线**：实时显示解析、分段、结构抽取、50300 挂载、模型复核、审计和落盘阶段；
- **结果修订**：在右侧面板修改抽取字段，保存后写回 `result.json`，并在事件流中留下修订记录；
- **透明落盘**：每个任务独立保存源文件、`job.json`、`events.jsonl` 和 `result.json`。

### 最快体验

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[server,pdf]"
acceptance-ext serve
```

命令会打开 `http://127.0.0.1:8000/editor`。页面里的“执行示例”不依赖 PDF 解析器，可直接观看完整 Job 流程。

处理扫描件或复杂版面时，可安装并选择其他 parser：

```bash
pip install -e ".[server,docling]"
```

MinerU 与 PaddleOCR 通过外部命令接入：

```bash
export MINERU_COMMAND='your-command --input {input} --output {output}'
export PADDLEOCR_COMMAND='your-command --input {input} --output {output}'
```

Job 默认保存在仓库根目录的 `.acceptance_ext/jobs/`。可指定独立工作区：

```bash
acceptance-ext serve --workspace ./runtime
```

API 文档位于 `/api/docs`。

## CLI

```bash
acceptance-ext extract sample_data/mini_standard.md \
  --parser markdown \
  --extractor heuristic \
  --output output/result.json \
  --review-html output/review.html
```

对多个解析器/抽取器做同文档对比：

```bash
acceptance-ext benchmark sample_data/mini_standard.md \
  --parsers markdown \
  --extractors heuristic,openai-compatible \
  --output output/benchmark.json
```

## 输出契约

核心结果由 Pydantic 模型约束：

```text
ResultDocument
└── DivisionItem（分项）
    └── InspectionLot（检验批）
        └── AcceptanceItem（验收项目）
            └── Evidence（原文、页码、bbox、行号、字符区间）
```

每次运行还会生成 `audit` 与 `metrics`，用于检查缺失证据、未挂载节点、重复项目、抽样规则覆盖率和执行耗时。

## 开发

```bash
pip install -e ".[server,pdf,dev]"
pytest
ruff check src tests
```

当前 Web Job 采用线程池与阶段间协作取消，适合本地实验和执行体验验证；它还不是多机生产调度器，暂不支持运行中暂停/恢复。
