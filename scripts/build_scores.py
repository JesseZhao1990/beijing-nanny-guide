"""Merge individually reviewed ratings; never infer a rating from keywords."""
from pathlib import Path
from collections import Counter
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[1]
data_path = ROOT / 'dist/data.json'
data = json.loads(data_path.read_text())
rubric = json.loads((ROOT / 'scoring/rubric.json').read_text())
reviews = []
for batch in ('01-40', '41-82', '83-125'):
    reviews.extend(json.loads((ROOT / f'scoring/reviews-{batch}.json').read_text()))
assert len(reviews) == len(data['items']) == 125
assert len({r['id'] for r in reviews}) == 125
reviews_by_id = {r['id']: r for r in reviews}
weights = [d['weight'] for d in rubric['dimensions']]
assert sum(weights) == 100
presets = [
    {'id': 'balanced', 'name': '默认 · 换人与退出占50%', 'weights': weights},
    {'id': 'replacement', 'name': '更看重换人 · 换人与退出占65%', 'weights': [40,25,10,10,10,5]},
    {'id': 'staff', 'name': '更看重筛选 · 人员筛选占30%', 'weights': [20,15,30,15,10,10]},
]
for item in data['items']:
    r = reviews_by_id[item['id']]
    for key in ('levels', 'reasons', 'sourceRefs'):
        assert len(r[key]) == 6, (item['id'], key)
    assert all(type(n) is int and 0 <= n <= 4 for n in r['levels']), item['id']
    assert all(len(s) >= 15 for s in r['reasons']) and len(r['summary']) >= 15, item['id']
    if item['businessStatus'] != 'confirmed':
        assert r['levels'][4] <= 1, item['id']
    for level, refs in zip(r['levels'], r['sourceRefs']):
        assert isinstance(refs, list)
        if level:
            assert refs, (item['id'], 'positive level needs source')
        for ref in refs:
            assert re.fullmatch(r's[1-9][0-9]*', ref), (item['id'], ref)
            assert int(ref[1:]) <= len(item['research']['sources']), (item['id'], ref)
    item['scorecard'] = {key:r[key] for key in ('levels','reasons','sourceRefs','summary')}
    item['scorecard']['total'] = sum(n*w//5 for n,w in zip(r['levels'], weights))
    item['scorecard']['covered'] = sum(n>0 for n in r['levels'])

eligible = sorted((i for i in data['items'] if i['businessStatus']=='confirmed'), key=lambda i:-i['scorecard']['total'])
for item in data['items']:
    score = item['scorecard']
    score['rank'] = 1+sum(i['scorecard']['total']>score['total'] for i in eligible) if item['businessStatus']=='confirmed' else None
    score['tied'] = sum(i['scorecard']['total']==score['total'] for i in eligible)>1 if score['rank'] else False

data['scoring'] = {key:rubric[key] for key in ('version','name','evidenceAsOf','dimensions','rules')}
data['scoring']['presets'] = presets
data['scoring']['method'] = '逐家判读六维证据；按档位和权重汇总。权重为本手册的选择偏好，不是行业认证或统计拟合。'
data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

labels = {'confirmed':'北京育儿业务有线索','pending':'业务待确认，不进主榜','platform':'平台入口，不进主榜'}
rows = []
for item in sorted(data['items'], key=lambda i:(['confirmed','pending','platform'].index(i['businessStatus']),-i['scorecard']['total'],i['id'])):
    s=item['scorecard']
    row={'机构':item['name'],'比较分组':labels[item['businessStatus']],'默认保障资料参考分':s['total'],'主榜名次':s['rank'] or '',
         '并列': '是' if s['tied'] else '否','有加分依据维度数':s['covered'],'总维度数':6,'评分说明':s['summary'],
         '口碑提示（不计入分数）':item['reputation'],'证据截至':rubric['evidenceAsOf'],'模型版本':rubric['version']}
    for index,d in enumerate(rubric['dimensions']):
        row[d['name']+'得分（满分'+str(d['weight'])+'）']=s['levels'][index]*d['weight']//5
        row[d['name']+'档位（0–5）']=s['levels'][index]
        row[d['name']+'依据与缺口']=s['reasons'][index]
        row[d['name']+'来源']='\n'.join(item['research']['sources'][int(ref[1:])-1]['url'] for ref in s['sourceRefs'][index])
    rows.append(row)
with (ROOT/'dist/scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)

# Keep the existing full research download and append the default model results.
research_path=ROOT/'dist/research.csv'
with research_path.open(encoding='utf-8-sig',newline='') as f:
    research_rows=list(csv.DictReader(f))
by_name={i['name']:i for i in data['items']}
for row in research_rows:
    item=by_name[row['机构/品牌']]
    score=item['scorecard']
    row.pop('默认保障参考分（100分）', None)
    if '联系批次' in row:
        row['原调查联系批次（评分前）']=row.pop('联系批次')
    row['默认保障资料参考分（100分）']=score['total']
    row['机构主榜名次（同分并列）']=score['rank'] or '不进入主榜'
    row['有加分依据项（6项）']=score['covered']
    row['评分摘要']=score['summary']
    row['评分版本']='v'+rubric['version']
with research_path.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(research_rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(research_rows)

print(json.dumps({'scored':len(rows),'groups':dict(Counter(i['businessStatus'] for i in data['items'])),
                  'top10':[(i['name'],i['scorecard']['total']) for i in eligible[:10]]},ensure_ascii=False,indent=2))
