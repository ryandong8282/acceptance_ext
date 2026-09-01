# Evaluation protocol

A parser/extractor is not considered stronger because its demo looks polished. Use the same source files, the same ontology and a frozen human-labelled gold set.

Minimum reported metrics:

1. acceptance-item precision, recall and F1;
2. exact source-clause and source-quote grounding rate;
3. minimum-sampling exact/normalized accuracy;
4. item-category accuracy;
5. GB 50300 attachment accuracy and wrong-attachment rate;
6. duplicate and hallucinated item count;
7. elapsed time, model calls, token usage and monetary cost;
8. human correction time per document.

Split standards by document type (native text, scanned, table-heavy) and by standard family. Keep parser output, prompts, model version, task spec and ontology hash with every run.
