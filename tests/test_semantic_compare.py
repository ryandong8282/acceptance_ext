from acceptance_ext.semantic_compare import compare_pdfex_documents


def test_compare_pdfex_documents_exact():
    item={"name":"模板的起拱","node_type":"验收项目","source_clause":"4.2.7","item_category":"一般项目","check_method":"水准仪或尺量","min_sampling":"全数或10%","source_quote":"原文","verification_sources":[{"quote":"原文"}],"children":[]}
    doc={"tree":[{"name":"主体结构","children":[{"name":"混凝土结构","children":[{"name":"模板","children":[{"name":"模板安装检验批","children":[item]}]}]}]}]}
    result=compare_pdfex_documents(doc,doc)
    assert result["item_f1"]==1.0
    assert result["field_accuracy"]["check_method"]==1.0
    assert result["candidate_grounding_rate"]==1.0
