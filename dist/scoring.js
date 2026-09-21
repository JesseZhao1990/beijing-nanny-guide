'use strict';
(function(root){
  function calculate(levels, weights) {
    if (!Array.isArray(levels) || levels.length !== weights.length) throw new Error('评分维度不完整');
    if (weights.reduce((a,b)=>a+b,0)!==100 || weights.some(w=>w<0)) throw new Error('权重必须合计100');
    if (levels.some(n=>!Number.isInteger(n)||n<0||n>5)) throw new Error('档位超出范围');
    const components=levels.map((n,i)=>Math.round(n/5*weights[i]*10)/10);
    return {components,total:Math.round(components.reduce((a,b)=>a+b,0)*10)/10,covered:levels.filter(n=>n>0).length};
  }
  function rank(items, weights) {
    const eligible=items.filter(r=>r.businessStatus==='confirmed'&&r.scorecard)
      .map(r=>({id:r.id,total:calculate(r.scorecard.levels,weights).total}))
      .sort((a,b)=>b.total-a.total||a.id.localeCompare(b.id));
    const result={};
    eligible.forEach((r,i)=>{
      const first=eligible.findIndex(x=>x.total===r.total);
      result[r.id]={position:first+1,tied:eligible.filter(x=>x.total===r.total).length>1};
    });
    return result;
  }
  const api={calculate,rank};
  root.NannyScoring=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window==='undefined'?globalThis:window);
