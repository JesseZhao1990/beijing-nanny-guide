"""Rebuild government-primary comparison from reviewed source and identity mappings."""
from pathlib import Path
from collections import Counter
import csv
import json
import re

ROOT=Path(__file__).resolve().parents[1]
def read(path): return json.loads((ROOT/path).read_text())
def write(path,obj): (ROOT/path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
data=read('dist/data.json')
rubric=read('scoring/rubric.json')
sources=read('research/government/sources.json')
mapping=read('research/government/mapping.json')
reviews=sum((read(f'scoring/reviews-{batch}.json') for batch in ('01-40','41-82','83-125')),[])
assert len(data['items'])==len(mapping)==len(reviews)==125
by_id={r['id']:r for r in reviews};mapped={r['id']:r for r in mapping}
assert len(mapped)==len(by_id)==125
source_by_type={s['recordType']:s for s in sources if s.get('recordType')}
points={'labor-brand-2025':60,'employee-2024':15,'employee-2023':10,'input-base-2025':10}
labels={'official':'政府品牌推选优先组','historical':'其他政府记录组','supplement':'未匹配入选名单的补充组','identity':'主体待核组','business':'北京育儿业务待核组','platform':'平台入口组'}
order=list(labels)
for item in data['items']:
    old=by_id[item['id']];m=mapped[item['id']]
    assert m['name']==item['name']
    assert all(len(old[k])==6 for k in ('levels','reasons','sourceRefs'))
    matches=[]
    for match in m['governmentMatches']:
        src=source_by_type[match['recordType']]
        assert match['listedCompany'] in src['companies'],(item['id'],match['listedCompany'],src['sourceId'])
        assert match['matchStatus'] in ('exact','brand-linked','pending')
        matches.append({**match,'sourceId':src['sourceId'],'title':src['title'],'url':match['sourceUrl'],
                        'listUrl':src['url'],'year':src['year'],'nature':src['nature'],'validity':src['validity'],
                        'points':points[match['recordType']] if match['matchStatus']!='pending' else 0})
    gov=max((m['points'] for m in matches),default=0)
    if item['businessStatus']=='platform': group='platform'
    elif item['businessStatus']!='confirmed' or m.get('businessGate')=='hold': group='business'
    elif m['entityGate']!='pass': group='identity'
    elif gov==60: group='official'
    elif gov>0: group='historical'
    else: group='supplement'
    best=next((x for x in matches if x['points']==gov and x['points']>0),None)
    if best:
        summary=f"{labels[group]}。对应{best['year']}年{best['nature']}，列名公司为{best['listedCompany']}。"
        if best['recordType']=='labor-brand-2025': summary+='名单没有官方名次；仍须核对本单合同、育儿人选与换人条款。'
        elif best['recordType'].startswith('employee'): summary+='该年度员工制认定已过一年有效期，只记历史入选。'
        else: summary+='劳务输入基地反映人员对接功能，不等于育儿服务质量认证。'
        if best['matchStatus']=='brand-linked': summary+='这是品牌关联记录，仅适用于列名法人，不覆盖所有同品牌订单。'
    else: summary=f"{labels[group]}。本轮逐一对照四份正式政府名单，未取得可归属的入选记录；不等于机构差或不存在其他荣誉。"
    if m.get('shortCaution'): summary+=m['shortCaution']
    if group in ('identity','business','platform'): summary+='不进入政府品牌推选优先组；数值仅供查看已有资料构成。'
    item['officialSelection']={'group':group,'groupLabel':labels[group],'points':gov,'identityGate':m['entityGate'],
      'identityReason':m['reason'],'businessGate':m.get('businessGate'),'businessReason':m.get('businessReason'),'matches':matches,'summary':summary,'checkedAt':rubric['evidenceAsOf']}
    # Preserve the independent manual evidence assessments; government is category based, not a service evidence level.
    indices=[0,1,2,3,5]
    levels=[gov/12]+[old['levels'][i] for i in indices]
    reasons=[summary]+[old['reasons'][i] for i in indices]
    refs=[[]]+[old['sourceRefs'][i] for i in indices]
    for level, sr in zip(levels[1:],refs[1:]):
        assert type(level) is int and 0<=level<=4
        assert not level or sr
        for ref in sr:
            assert re.fullmatch(r's[1-9][0-9]*',ref)
            assert int(ref[1:])<=len(item['research']['sources'])
    components=[gov]+[levels[i+1]/5*w for i,w in enumerate([15,10,5,5,5])]
    item['scorecard']={'levels':levels,'reasons':reasons,'sourceRefs':refs,'summary':summary,
        'serviceSummary':old['summary'],'components':components,'total':round(sum(components),1),
        'covered':sum(n>0 for n in components),'rank':None,'tied':False}
    # Changing ranking must not rewrite any research, complaints, or sources.

eligible=[r for r in data['items'] if r['officialSelection']['group']=='official']
for item in eligible:
    score=item['scorecard'];score['rank']=1+sum(r['scorecard']['total']>score['total'] for r in eligible)
    score['tied']=sum(r['scorecard']['total']==score['total'] for r in eligible)>1

data['scoring']={k:rubric[k] for k in ('version','name','evidenceAsOf','dimensions','rules')}
data['scoring'].update({'presets':[{'id':'government','name':'政府推选优先 · 政府60 / 保障40','weights':[60,15,10,5,5,5]}],
  'method':'先按政府记录与主体/业务门槛分组，政府品牌推选优先组内部再按保障资料排序；不是政府排名。',
  'officialSources':sources,'groups':[{'id':g,'label':labels[g],'count':sum(r['officialSelection']['group']==g for r in data['items'])} for g in labels],
  'governmentSourceLimit':'对照2025品牌、2025输入基地、2024与2023员工制正式名单；截至2026-09-21未取得2025/2026员工制最终更新名单或较新星级企业结果，不把未检出当不存在。'})
write('dist/data.json',data)

def sorted_items(): return sorted(data['items'],key=lambda r:(order.index(r['officialSelection']['group']),-r['scorecard']['total'],r['id']))
rows=[]
for r in sorted_items():
    s=r['scorecard'];g=r['officialSelection']
    row={'机构':r['name'],'比较分组':g['groupLabel'],'政府优先参考分（100分）':s['total'],'政府品牌组内次序（非官方排名）':s['rank'] or '',
      '并列':'是' if s['tied'] else '否','政府依据分（60）':g['points'],'服务保障资料分（40）':sum(s['components'][1:]),
      '主体门槛':g['identityGate'],'主体核对说明':g['identityReason'],'政府完整法人':'\n'.join(m['listedCompany'] for m in g['matches']),
      '政府记录年份及性质':'\n'.join(f"{m['year']} {m['nature']}" for m in g['matches']),
      '政府依据链接':'\n'.join(m['url'] for m in g['matches']),'政府有效期说明':'\n'.join(str(m['validity']) for m in g['matches']),
      '品牌与法人对应':'\n'.join(m['matchBasis'] for m in g['matches']),'评分说明':s['summary'],
      '保障资料原判读摘要':s['serviceSummary'],'本轮投诉补查':r.get('complaintAudit',{}).get('summary',''),
      '12315公示核查':r.get('governmentAudit',{}).get('summary',''),'证据截至':rubric['evidenceAsOf'],'模型版本':rubric['version']}
    for i,d in enumerate(rubric['dimensions'][1:],1):
        row[d['name']+f"得分（满分{d['weight']}）"]=s['components'][i]
        row[d['name']+'依据与缺口']=s['reasons'][i]
        row[d['name']+'来源']='\n'.join(r['research']['sources'][int(ref[1:])-1]['url'] for ref in s['sourceRefs'][i])
    rows.append(row)
def csvwrite(path,rows):
    with (ROOT/path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
csvwrite('dist/scores.csv',rows)
with (ROOT/'dist/research.csv').open(encoding='utf-8-sig',newline='') as f: research=list(csv.DictReader(f))
byname={r['name']:r for r in data['items']}
for row in research:
    r=byname[row['机构/品牌']];s=r['scorecard'];g=r['officialSelection']
    for stale in ['默认保障资料参考分（100分）','机构主榜名次（同分并列）','有加分依据项（6项）']:
        row.pop(stale,None)
    row.update({'政府优先参考分（100分）':s['total'],'政府比较分组':g['groupLabel'],
      '政府品牌组内次序（非官方排名）':s['rank'] or '不进入政府品牌优先组',
      '政府依据分（60）':g['points'],'政府完整法人':'\n'.join(m['listedCompany'] for m in g['matches']),
      '政府依据链接':'\n'.join(m['url'] for m in g['matches']),'评分摘要':s['summary'],'评分版本':'v2.0'})
csvwrite('dist/research.csv',research)
print(json.dumps({'version':'2.0','scored':len(rows),'groups':dict(Counter(r['officialSelection']['group'] for r in data['items'])),
  'officialTop10':[(r['name'],r['scorecard']['total']) for r in sorted_items() if r['officialSelection']['group']=='official'][:10]},ensure_ascii=False,indent=2))
