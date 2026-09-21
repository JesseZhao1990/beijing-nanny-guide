'use strict';
let scorePreset='balanced';
const scoringMeta=()=>DATA.scoring;
const currentPreset=()=>scoringMeta().presets.find(p=>p.id===scorePreset)||scoringMeta().presets[0];
const scoreValue=r=>NannyScoring.calculate(r.scorecard.levels,currentPreset().weights);
const scoreGroup=r=>({confirmed:'北京育儿业务有线索',pending:'业务待确认',platform:'平台入口'})[r.businessStatus];
const scoreGate=r=>r.scorecard.levels[4]<3?'<span class="score-gate">先核主体与北京接单</span>':'';
const scoreState=level=>level===0?'未取得加分依据':level===1?'有限线索':'有具体公开资料';
function scoreRankText(r,ranks){const rank=ranks[r.id];return rank?`总分${rank.tied?'并列 ':''}第 ${rank.position} 名`:'不进机构主榜';}
function scoreBadge(r){const s=scoreValue(r);return `<span class="score-badge"><b>${s.total}</b><span>/ 100</span></span><span class="table-sub">${s.covered} / 6 项有加分依据</span>${scoreGate(r)}`;}
function scoreGrid(r){const s=scoreValue(r);return `<div class="score-component-grid">${scoringMeta().dimensions.map((d,i)=>`<div><span>${esc(d.name)}</span><b>${s.components[i]}<small> / ${currentPreset().weights[i]}</small></b><span class="score-mini-track" aria-hidden="true"><i style="width:${r.scorecard.levels[i]*20}%"></i></span></div>`).join('')}</div>`;}
function scoreBreakdown(r){const s=scoreValue(r),m=scoringMeta();return `<section class="score-detail" aria-label="${esc(r.name)}评分依据"><div class="score-detail-heading"><div><p class="eyebrow">保障资料参考分</p>${scoreBadge(r)}</div><div><strong>${esc(currentPreset().name)}</strong><p>资料截至 ${esc(m.evidenceAsOf)} · 模型 v${esc(m.version)}<br>${esc(scoreGroup(r))}${r.businessStatus!=='confirmed'?' · 不进入机构主榜':''}</p></div></div><p>${esc(r.scorecard.summary)}</p><p class="score-boundary">没有及格线；0 分表示没有适用的正向加分依据，可能缺资料或条款不提供保障，具体看理由。分数衡量公开资料支持程度，不是服务质量或满意度。仍需核验本单合同和实际候选。</p>${scoreGrid(r)}<details class="score-reasons"><summary>展开六项打分理由与来源</summary>${m.dimensions.map((d,i)=>`<article><div class="score-reason-heading"><h4>${esc(d.name)}</h4><b>${s.components[i]} / ${currentPreset().weights[i]} 分</b></div><p class="score-level">${r.scorecard.levels[i]} / 5 档 · ${scoreState(r.scorecard.levels[i])}</p><p>${esc(r.scorecard.reasons[i])}</p><p class="score-criterion"><strong>所用标准：</strong>${esc(d.levels[r.scorecard.levels[i]])}</p><div>${r.scorecard.sourceRefs[i].length?r.scorecard.sourceRefs[i].map(ref=>{const src=r.research.sources[Number(ref.slice(1))-1];return `<a class="source-link" href="${esc(src.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.toUpperCase())} · ${esc(src.title)} ↗</a><span class="micro">${esc(src.type||'公开资料')} · ${esc(src.readStatus||'读取边界见档案')}</span>`;}).join(''):'<p class="micro">本轮检索未取得该项适用条款；原始检索记录保留在本档案下方。</p>'}</div></article>`).join('')}</details></section>`;}
function setupScores(){
 const m=scoringMeta();
 $('#scores').innerHTML=head('SCORING FRAMEWORK','给每一家，都列出分数和理由','围绕换人和退出保障，用同一套标准比较。先看分数由什么支持，再看是否值得索取合同。')+
 `<div class="score-overview"><div><b>${items.length}</b><span>条目均有六维评分</span></div><div><b>100</b><span>分制，权重可切换</span></div><div><b id="score-core-weight">50%</b><span>换人与退出的权重</span></div></div>
 <div class="score-notice"><strong>这是一套保障资料评分，分数不是机构服务质量。</strong><p>0 分表示未取得正向加分依据：可能缺资料，也可能条款不提供该保障，逐项理由会说明区别。资料缺失本身不代表服务差。商家自述可以成为有限加分依据，但不证明能履约。口碑单方叙述、投诉数量及“未搜到投诉”不直接计分。</p><p>目前未取得本单合同、拟派人员档案及替补库存，所以没有任何维度评为最高的 5 档；本轮资料条件下最多可得 80 分，没有及格线。业务待确认与平台入口单独查看。</p></div>
 <div class="score-settings"><label for="score-preset">你更看重什么</label><select id="score-preset">${m.presets.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}</select><p>切换权重会同步更新总分、主榜顺序、首页和详情；不会改变原始证据档位。</p><div id="score-weights" class="weight-pills"></div></div>
 <details class="method scoring-method"><summary>查看完整打分标准、证据门槛与局限</summary><p><strong>总分 = 六项（证据档位 ÷ 5 × 对应权重）之和。</strong>每项用 0–5 档逐项判读，未用关键词、搜索排名或来源数量自动决定档位。权重反映这次选择偏好，不是行业认证或经验证的预测模型。</p><p>默认权重：换人 30、退出 20、筛选 15、售后 15、主体业务 10、费用 10。更低价格、更多门店、入选官方名录不直接增加保障分。不同证据完整度的分数应结合缺口一起看。</p><p>机构官网与可归属的机构自有商家页采用相同尺度。仅旧资料、第三方推广或未读全文摘录，相关保障维度最多 1 档；纯招聘工资不当作家庭报价；仅有不退限制、取消收费不明、期满返保证金，不当作退出退费保障。异地、异工种、近名机构材料不移用。主体与业务可由政府/协会等交叉线索给 2 档。</p><p>主榜只比较北京育儿业务有线索的条目。同分并列，下一名按竞赛排名跳号；一两分差异不代表可测量的服务差距。口碑材料放在分数旁供核实，不按条数奖惩，也不计算投诉率。</p>${m.dimensions.map(d=>`<details class="dimension-rubric"><summary>${esc(d.name)} · 默认 ${d.weight} 分</summary><ol start="0">${d.levels.map((t,i)=>`<li><b>${i} 档</b> ${esc(t)}</li>`).join('')}</ol></details>`).join('')}<p class="micro">资料快照：${esc(m.evidenceAsOf)}；评分模型：v${esc(m.version)}。未联系机构、未验证现行待签合同、未试工。新证据出现后应重新评档。</p></details>
 <div class="section-heading"><h2>逐家评分与比较</h2><a class="source-link" href="scores.csv" download>下载默认权重评分 CSV ↓</a></div>
 <div class="filters score-filters"><label class="search-label"><span>搜索机构</span><input id="score-search" type="search" placeholder="机构、主体或区域"></label><label><span>比较分组</span><select id="score-group"><option value="confirmed">北京育儿业务有线索 · ${items.filter(r=>r.businessStatus==='confirmed').length}</option><option value="pending">业务待确认 · ${items.filter(r=>r.businessStatus==='pending').length}</option><option value="platform">平台入口 · ${items.filter(r=>r.businessStatus==='platform').length}</option><option value="all">全部已评分 · ${items.length}</option></select></label><label><span>机构类型</span><select id="score-category"><option value="all">全部类型</option>${[...new Set(items.map(r=>r.category))].map(t=>`<option>${esc(t)}</option>`).join('')}</select></label><label><span>排序方式</span><select id="score-sort"><option value="total">保障资料参考分从高到低</option><option value="replacement">换人保障从高到低</option><option value="refund">退出退费从高到低</option><option value="vetting">人员筛选从高到低</option><option value="coverage">有依据的维度从多到少</option></select></label></div>
 <div class="results-line"><p id="score-count" role="status" aria-live="polite"></p><button class="text-button" id="score-reset">重置评分筛选</button></div><p class="micro" id="score-group-note"></p><div id="score-results"></div>`;
 $('#scores .page-heading').insertAdjacentHTML('beforeend','<button class="outline-button" id="jump-score-list">直接看机构得分 ↓</button>');
 $('#jump-score-list').addEventListener('click',()=>$('#score-results').scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));
 $('#score-preset').addEventListener('change',e=>{scorePreset=e.target.value;renderScores();renderShortlist();renderDirectoryRows();});
 ['score-search','score-group','score-category','score-sort'].forEach(id=>$('#'+id).addEventListener('input',renderScores));
 $('#score-reset').addEventListener('click',()=>{$('#score-search').value='';$('#score-group').value='confirmed';$('#score-category').value='all';$('#score-sort').value='total';renderScores();});
 renderScores();
}
function renderScores(){
 const m=scoringMeta(),preset=currentPreset(),ranks=NannyScoring.rank(items,preset.weights),q=$('#score-search').value.trim().toLowerCase(),group=$('#score-group').value,category=$('#score-category').value,sort=$('#score-sort').value;
 $('#score-weights').innerHTML=m.dimensions.map((d,i)=>`<span>${esc(d.name)} <b>${preset.weights[i]}%</b></span>`).join('');
 $('#score-core-weight').textContent=(preset.weights[0]+preset.weights[1])+'%';
 const list=items.filter(r=>(group==='all'||r.businessStatus===group)&&(category==='all'||r.category===category)&&(!q||[r.name,r.entity,r.address,r.contact].join(' ').toLowerCase().includes(q))).sort((a,b)=>{
  const order={confirmed:0,pending:1,platform:2};
  if(group==='all'&&a.businessStatus!==b.businessStatus)return order[a.businessStatus]-order[b.businessStatus];
  const sa=scoreValue(a),sb=scoreValue(b),index=m.dimensions.findIndex(d=>d.key===sort);
  const specific=sort==='coverage'?sb.covered-sa.covered:index>=0?sb.components[index]-sa.components[index]:0;
  return specific||sb.total-sa.total||a.id.localeCompare(b.id);
 });
 $('#score-count').textContent=`显示 ${list.length} / ${items.length} 个已评分条目 · ${preset.name}`;
 $('#score-group-note').textContent=group==='confirmed'?'名次按当前权重下全部北京育儿业务有线索的机构计算；搜索或类型筛选不会改变名次。':group==='all'?'先显示机构主榜，再显示业务待确认和平台入口；不同组不混排。其他两组数字仅表示现有可归属资料的支持程度。':'当前分组不参与机构主榜；先核实北京育儿服务、签约和换人责任主体，再比较分数。';
 let previousGroup='';
 $('#score-results').innerHTML=list.length?list.map(r=>{
  const separator=group==='all'&&r.businessStatus!==previousGroup?`<h3 class="score-group-heading">${esc(scoreGroup(r))}</h3>`:'';previousGroup=r.businessStatus;
  return separator+`<article class="score-row"><div class="score-row-main"><span class="score-rank">${scoreRankText(r,ranks)}</span><button class="name-button" data-agency="${esc(r.id)}">${esc(name(r.name))}</button><span class="table-sub">${esc(r.category)} · ${esc(scoreGroup(r))}</span><div class="score-row-number">${scoreBadge(r)}</div></div><div class="score-row-body">${scoreGrid(r)}<p class="score-summary">${esc(r.scorecard.summary)}</p><details class="score-reputation" open><summary>口碑与履约提示 · 不计入分数</summary><p>${esc(reputationSummary(r))}</p>${r.complaintAudit?'<a class="source-link" href="#complaints">查看投诉与处理、逐家来源 →</a>':''}</details><div class="score-row-bottom">${openButton(r,'看六项评分依据与来源')}<span class="micro">0分原因见逐项依据</span></div></div></article>`;
 }).join(''):'<div class="empty">没有符合条件的条目，试试重置筛选。</div>';
}
function renderScoredShortlist(){
 const ranks=NannyScoring.rank(items,currentPreset().weights);
 const ranked=items.filter(r=>r.businessStatus==='confirmed').sort((a,b)=>scoreValue(b).total-scoreValue(a).total||a.id.localeCompare(b.id));
 $('#shortlist-heading').textContent='按保障资料参考分，先比较这些机构';
 $('#shortlist-caption').textContent=currentPreset().name+' · 同分并列，详见评分页';
 $('#shortlist-content').innerHTML=ranked.slice(0,4).map(r=>`<article class="agency-card"><div class="card-top"><span class="score-rank">${scoreRankText(r,ranks)}</span><span class="tag blue">${esc(r.category)}</span></div><h3>${esc(name(r.name))}</h3><div class="shortlist-score">${scoreBadge(r)}</div><p>${esc(r.scorecard.summary)}</p><div class="review-brief"><span>口碑提示 · 独立于分数</span>${esc(reputationSummary(r))}</div><p class="card-question">${esc(r.question)}</p>${openButton(r,'看得分依据与完整调查')}</article>`).join('');
 $('#shortlist-extra').innerHTML=`<div class="complaint-home"><strong>已补充多渠道投诉核查</strong><p>黑猫、消费保、12315官方公示与监管媒体记录，逐家查看处理结果和使用边界。</p><a class="outline-button" href="#complaints">查看投诉与处理 →</a></div><div class="platform-callout"><div><p class="eyebrow">125 SCORED DOSSIERS</p><h2>每家都有分数，每分都有依据</h2><p>六维评分、逐项理由、来源与口碑并排查看。主榜仅包含北京育儿业务有线索的机构，其余单独分组。</p></div><a class="outline-button" href="#scores">查看全部评分 →</a></div><div class="score-notice"><strong>高分意味着已取得更多具体保障资料，仍需核验能否履行。</strong><p>0 分项表示未取得正向加分依据，可能缺资料，也可能条款不提供保障。资料缺失本身不代表服务差。官网或商家说法没有经过实际订单验证。请结合口碑提示、现行合同和拟派人员一起判断。</p></div><div class="steps"><article><b>1</b><h3>先看分项缺口</h3><p>总分相近时，重点比较换人和退出两项，而不是只看名次。</p></article><article><b>2</b><h3>再拿合同核实</h3><p>把免费次数、同档差价、到岗期限和匹配失败退费写进本单合同。</p></article><article><b>3</b><h3>核验具体人选</h3><p>检查近期相同月龄经验、体检、背景及照护实操，并确认替补名单。</p></article></div>`;
}
