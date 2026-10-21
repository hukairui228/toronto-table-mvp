#!/usr/bin/env python3
"""Manual labels only. Blank labels excluded from denominator and reported separately."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
LABELS = ['探店合作','明显软广','素人真实','无法判断']

def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        if not any((v or '').strip() for v in row.values()): continue
        query=(row.get('query') or '').strip()
        if not query: raise ValueError('非空行缺少 query')
        label=(row.get('label') or '').strip()
        if label and label not in LABELS: raise ValueError(f'无效 label：{label}')
        grouped[query].append(label)
    def stats(labels):
        counts=Counter(labels); n=sum(counts[x] for x in LABELS)
        return {'total_rows':len(labels),'labeled':n,'unlabeled':counts[''],
            'categories':{label:{'count':counts[label],'share':counts[label]/n if n else None} for label in LABELS}}
    return {'by_query':{q:stats(labels) for q,labels in sorted(grouped.items())},
        'overall':stats([label for labels in grouped.values() for label in labels]),
        'method':'分母为已标注行数；无法判断参与分母，空白标签不参与；便利样本不能代表平台整体软广率。'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path,nargs='?',default=Path(__file__).with_name('labeling_template.csv'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    with args.input.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not set(['query','rank','post_title','author','label','notes']).issubset(reader.fieldnames or []):
            parser.error('缺少所需表头')
        result=summarize(list(reader))
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output: args.output.write_text(text+'\n',encoding='utf-8')
    print(text)
