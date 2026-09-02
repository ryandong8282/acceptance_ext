from pathlib import Path
from acceptance_ext.models import ParsedBlock, ResultDocument
from acceptance_ext.pdfex_contract import pdfex_payload_exact
from acceptance_ext.semantic_v2 import extract_tree_v2


def test_gb50204_chapter4_semantics_and_pdfex_contract(tmp_path: Path):
    text = '''# 4 模板分项工程 [PDF p.17]\n# 4.2 模板安装 [PDF p.17]\n主控项目\n4.2.3 后浇带处的模板及支架应独立设置。\n\n检查数量：全数检查。\n\n检验方法：观察。\n'''
    source=tmp_path/'x.md'; source.write_text(text,encoding='utf-8')
    block=ParsedBlock(text=text,source_file='x.md',source_hash='h',parser='markdown',page=17)
    tree,chapters=extract_tree_v2([block],source)
    tree[0].mapped_50300_path=['主体结构','混凝土结构','模板']
    doc=ResultDocument(source_pdf='x.pdf',standard_no='GB 50204-2015',standard_name='混凝土结构工程施工质量验收规范',parser='markdown',extractor='semantic-v2',chapters=chapters,tree=tree)
    payload=pdfex_payload_exact(doc)
    root=payload['tree'][0]; sub=root['children'][0]; division=sub['children'][0]; lot=division['children'][0]; item=lot['children'][0]
    assert (root['id'],root['type'],root['type_name'],root['node_type'])==(2,3,'分部','单位')
    assert (sub['id'],sub['type'],sub['type_name'])==(18,2,'子分部')
    assert (division['id'],division['type'],division['type_name'])==(161,1,'分项')
    assert item['source_clause']=='4.2.3'
    assert item['min_sampling_script']=='ALL()'
    assert item['min_sampling_json']['ysItem'][0]['Expression']=='lot_size'
    assert item['check_method']=='观察'
