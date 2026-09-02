from __future__ import annotations

import time
from pathlib import Path

from .evaluation import evaluate
from .exporters import write_json, write_pdfex, write_review_html
from .extraction import attach_ontology, extract_tree, infer_standard, load_task_spec
from .models import ResultDocument
from .parsers import get_parser
from .refinement import openai_compatible_refine
from .semantic_v2 import extract_tree_v2
from .validation import metrics, validate


class ExtractionPipeline:
    def __init__(self, parser: str = "markdown", extractor: str = "semantic-v2", ontology_path: Path | None = None, task_spec_path: Path | None = None) -> None:
        self.parser_name=parser; self.extractor_name=extractor; self.ontology_path=ontology_path; self.task_spec_path=task_spec_path

    def run(self, source: Path) -> ResultDocument:
        started=time.perf_counter(); parser=get_parser(self.parser_name); blocks=parser.parse(source)
        standard_no,standard_name=infer_standard(blocks,source.name)
        if self.extractor_name in {"semantic-v2","integrated","domain"}:
            tree,chapters=extract_tree_v2(blocks,source)
        else:
            tree=extract_tree(blocks,load_task_spec(self.task_spec_path)); chapters=[]
        attach_ontology(tree,self.ontology_path)
        pages=[block.page for block in blocks if block.page]
        document=ResultDocument(source_pdf=source.name,standard_no=standard_no,standard_name=standard_name,parser=self.parser_name,extractor=self.extractor_name,chapters=chapters,tree=tree,page_count=max(pages) if pages else None,markdown_file=source.name if source.suffix.lower() in {".md",".markdown"} else None)
        if self.extractor_name in {"openai","openai-compatible","llm"}:
            document=openai_compatible_refine(document)
        elif self.extractor_name not in {"heuristic","deterministic","semantic-v2","integrated","domain"}:
            raise ValueError("extractor must be semantic-v2, heuristic or openai-compatible")
        document.audit=validate(document); document.metrics=metrics(document,time.perf_counter()-started)
        return document

    def run_to_files(self, source: Path, output: Path, pdfex_output: Path | None = None, review_html: Path | None = None, gold: Path | None = None) -> tuple[ResultDocument,dict|None]:
        document=self.run(source); write_json(document,output)
        if pdfex_output: write_pdfex(document,pdfex_output,self.ontology_path)
        if review_html: write_review_html(document,review_html)
        score=evaluate(document,gold) if gold else None
        return document,score
