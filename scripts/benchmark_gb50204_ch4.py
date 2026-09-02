from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from acceptance_ext.models import ParsedBlock, ResultDocument
from acceptance_ext.pdfex_contract import pdfex_payload_exact
from acceptance_ext.semantic_v2 import extract_tree_v2


def compact(value: Any) -> str:
    return re.sub(r"[\s，。；：、（）()【】\[\]《》<>·—－_\-]+", "", str(value or "")).lower()


def name_score(a: str, b: str) -> float:
    a,b=compact(a),compact(b)
    if not a or not b: return 0.0
    if a==b or a in b or b in a: return 1.0
    aa={a[i:i+2] for i in range(max(1,len(a)-1))}; bb={b[i:i+2] for i in range(max(1,len(b)-1))}
    return 2*len(aa&bb)/max(1,len(aa)+len(bb))


def parse_script(script: str | None) -> list[dict[str, Any]]:
    if not script: return []
    result=[]
    for part in script.split(';'):
        m=re.match(r'(ALL|RATIO|EXTERNAL)\((.*)\)$',part.strip())
        if not m: continue
        d={'kind':{'ALL':'all','RATIO':'ratio','EXTERNAL':'external'}[m.group(1)],'scope':'','when':''}
        for key,quoted,number in re.findall(r'(\w+)=(?:"([^"]*)"|([0-9.]+))',m.group(2)):
            d[key]=int(float(number)) if key in {'pct','min'} and number else (quoted or number)
        result.append(d)
    return result


def branch_key(clause: str, b: dict[str, Any]) -> str:
    kind=b.get('kind',''); scope=compact(b.get('scope')); when=compact(b.get('when'))
    if when.endswith('时'): when=when[:-1]
    return '|'.join([clause,kind,scope,when,str(b.get('pct','')),str(b.get('min','')),str(b.get('unit','')),compact(b.get('text'))])


def candidate_v2(markdown: Path) -> tuple[dict[str, Any], ResultDocument]:
    text=markdown.read_text(encoding='utf-8-sig'); digest=hashlib.sha256(markdown.read_bytes()).hexdigest()
    block=ParsedBlock(text=text,source_file=markdown.name,source_hash=digest,parser='markdown')
    tree,chapters=extract_tree_v2([block],markdown)
    mapping={'模板分项工程':['主体结构','混凝土结构','模板']}
    for division in tree:
        if division.name in mapping: division.mapped_50300_path=mapping[division.name]
    doc=ResultDocument(source_pdf='GB 50204-2015 混凝土结构工程施工质量验收规范.pdf',standard_no='GB 50204-2015',standard_name='混凝土结构工程施工质量验收规范',parser='markdown',extractor='semantic-v2',chapters=chapters,tree=[d for d in tree if d.name=='模板分项工程'],page_count=142,markdown_file=markdown.name)
    items=[]; branches={}
    for division in doc.tree:
        for lot in division.children:
            for item in lot.children:
                if not (item.source_clause or '').startswith('4.2.'): continue
                items.append({'clause':item.source_clause,'name':item.name,'category':item.item_category,'check_method':item.check_method,'deviation_value':item.deviation_value})
                branches.setdefault(item.source_clause,parse_script(item.min_sampling_script))
    return {'name':'semantic-v2','items':items,'sampling_branches':branches,'contract_aligned':True},doc


def candidate_v01(markdown: Path) -> dict[str, Any]:
    text=markdown.read_text(encoding='utf-8-sig')
    start=text.find('# 4 模板分项工程 [PDF p.17]'); end=text.find('# 5 钢筋分项工程 [PDF p.22]',start); scoped=text[start:end]
    items=[]
    for m in re.finditer(r'(?m)^4\.2\.(?:[1-9]|10)\s+(.+)$',scoped):
        clause=m.group(0).split(maxsplit=1)[0]; body=m.group(1)
        if not re.search(r'应|必须|不得|严禁|符合.*规定|验收|检查|检验|允许偏差',body): continue
        name=re.sub(r'应.*$','',re.split(r'[。；]',body,maxsplit=1)[0]).strip(' ，。：；')[:48]
        num=int(clause.rsplit('.',1)[1]); items.append({'clause':clause,'name':name,'category':'一般项目' if num>=5 else '未分类','check_method':None,'deviation_value':None})
    return {'name':'public-v0.1-line-parser','items':items,'sampling_branches':{},'contract_aligned':False}


def score(gold: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    expected=gold['items']; predicted=candidate['items']; used=set(); pairs=[]; missing=[]
    for left in expected:
        best_i=None;best=0.0
        for i,right in enumerate(predicted):
            if i in used or left['clause']!=right['clause']: continue
            s=name_score(left['name'],right['name'])
            if s>best:best_i,best=i,s
        if best_i is None or best<.72: missing.append(left['key']); continue
        used.add(best_i);pairs.append((left,predicted[best_i]))
    extra=[f"{x['clause']}|{x['name']}" for i,x in enumerate(predicted) if i not in used]
    tp=len(pairs); p=tp/len(predicted) if predicted else 0; r=tp/len(expected) if expected else 0
    exp={branch_key(no,b) for no,rows in gold['sampling_branches'].items() for b in rows}; got={branch_key(no,b) for no,rows in candidate['sampling_branches'].items() for b in rows}
    return {'candidate':candidate['name'],'expected_item_count':len(expected),'predicted_item_count':len(predicted),'matched_item_count':tp,'item_precision':round(p,4),'item_recall':round(r,4),'item_f1':round(2*p*r/(p+r),4) if p+r else 0,'category_accuracy':round(sum(compact(a['category'])==compact(b['category']) for a,b in pairs)/tp,4) if tp else 0,'method_accuracy':round(sum(compact(a.get('check_method'))==compact(b.get('check_method')) for a,b in pairs)/tp,4) if tp else 0,'sampling_branch_recall':round(len(exp&got)/len(exp),4) if exp else 0,'pdfex_contract_aligned':candidate['contract_aligned'],'missing_items':missing,'extra_items':extra,'missing_sampling_branches':sorted(exp-got)}


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument('markdown',type=Path); parser.add_argument('--gold',type=Path,default=Path('benchmarks/gb50204_ch4/gold.json')); parser.add_argument('--output-dir',type=Path,default=Path('reports/generated/gb50204_ch4')); parser.add_argument('--ontology',type=Path,default=None); args=parser.parse_args()
    gold=json.loads(args.gold.read_text(encoding='utf-8-sig')); v2,doc=candidate_v2(args.markdown); v1=candidate_v01(args.markdown); scores=[score(gold,v1),score(gold,v2)]
    args.output_dir.mkdir(parents=True,exist_ok=True); (args.output_dir/'comparison.json').write_text(json.dumps({'scores':scores},ensure_ascii=False,indent=2),encoding='utf-8'); (args.output_dir/'acceptance_ext_v02.pdfex.json').write_text(json.dumps(pdfex_payload_exact(doc,args.ontology),ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(scores,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
