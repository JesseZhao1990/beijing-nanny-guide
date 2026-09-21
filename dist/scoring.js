'use strict';
(function(root){
  const groups=['official','historical','supplement','identity','business','platform'];
  function calculate(levels, weights) {
    if (!Array.isArray(levels) || levels.length !== weights.length) throw new Error('评分维度不完整');
    if (weights.reduce((a,b)=>a+b,0)!==100 || weights.some(w=>w<0)) throw new Error('权重必须合计100');
    if (levels.some(n=>!Number.isFinite(n)||n<0||n>5)) throw new Error('档位超出范围');
    const components=levels.map((n,i)=>Math.round(n/5*weights[i]*10)/10);
    return {components,total:Math.round(components.reduce((a,b)=>a+b,0)*10)/10,covered:levels.filter(n=>n>0).length};
  }
  function score(r) {
    const components=[r.officialSelection.points,...r.scorecard.levels.slice(1).map((n,i)=>n/5*[15,10,5,5,5][i])];
    return {components,total:Math.round(components.reduce((a,b)=>a+b,0)*10)/10,covered:components.filter(n=>n>0).length};
  }
  function eligible(r){return r.businessStatus==='confirmed'&&r.officialSelection.identityGate==='pass'&&r.officialSelection.group==='official';}
  function compare(a,b){return groups.indexOf(a.officialSelection.group)-groups.indexOf(b.officialSelection.group)||score(b).total-score(a).total||a.id.localeCompare(b.id);}
  function rank(items) {
    const selected=items.filter(eligible).sort(compare), result={};
    selected.forEach(r=>{const total=score(r).total;result[r.id]={position:1+selected.filter(x=>score(x).total>total).length,tied:selected.filter(x=>score(x).total===total).length>1};});
    return result;
  }
  const api={calculate,score,eligible,compare,rank,groups};
  root.NannyScoring=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window==='undefined'?globalThis:window);
