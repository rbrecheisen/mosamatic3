(() => {
  const dataNode = document.getElementById('va-cohort-data');
  const workspace = document.getElementById('va-workspace');
  const preopConfigNode = document.getElementById('va-preoperative-config');
  if (!dataNode || !workspace || !preopConfigNode) return;
  let cohort, preopConfig;
  try {
    cohort = JSON.parse(dataNode.textContent);
    preopConfig = JSON.parse(preopConfigNode.textContent);
  } catch (_) { return; }
  if (!cohort || !Array.isArray(cohort.rows) || !cohort.rows.length) return;

  const xSel = document.getElementById('va-x');
  const ySel = document.getElementById('va-y');
  const outSel = document.getElementById('va-outcome');
  const status = document.getElementById('va-status');
  const note = document.getElementById('va-note');
  const chartEl = document.getElementById('va-chart');
  workspace.hidden = false;
  status.textContent = `${cohort.filename} · ${cohort.sheet} · ${cohort.rows.length} patients · ${cohort.columns.length} variables`;

  const numeric = cohort.columns.filter(c => {
    const vals = cohort.rows.map(r => r[c]).filter(v => v !== null && v !== '' && v !== undefined);
    if (!vals.length) return false;
    return vals.filter(v => Number.isFinite(Number(v))).length / vals.length >= 0.75;
  });
  const outcomes = cohort.columns.filter(c => {
    const vals = cohort.rows.map(r => r[c]).filter(v => v !== null && v !== '' && v !== undefined);
    return vals.length && new Set(vals.map(String)).size <= 12;
  });
  function fill(sel, cols) { cols.forEach(c => { const o=document.createElement('option'); o.value=c; o.textContent=c; sel.appendChild(o); }); }
  fill(xSel, numeric); fill(ySel, numeric); fill(outSel, outcomes.filter(c => !numeric.includes(c) || new Set(cohort.rows.map(r=>r[c]).filter(v=>v!==null)).size <= 12));
  const pick = (sel, names, fallback=0) => { const n=names.find(v => [...sel.options].some(o=>o.value===v)); if(n) sel.value=n; else if(sel.options[fallback]) sel.selectedIndex=fallback; };
  pick(xSel, ['smra','muscle_ra','muscle_attenuation'], 0);
  pick(ySel, ['CRP','crp'], Math.min(1, ySel.options.length-1));
  pick(outSel, ['major.complications','CRPOPF','CRPPH','DEATH 90d'], 0);

  // Exploratory supervised screening controls. Candidate/anchor variables are restricted
  // to the explicit preoperative allow-list supplied by the server configuration.
  const preopNames = new Set((preopConfig && Array.isArray(preopConfig.variables)) ? preopConfig.variables : []);
  const preopNumeric = numeric.filter(c => preopNames.has(c));
  const anchorSel = document.getElementById('va-anchor');
  const screenOutcomeSel = document.getElementById('va-screen-outcome');
  const screenButton = document.getElementById('va-find-combinations');
  const screenNote = document.getElementById('va-screen-note');
  const screenChartEl = document.getElementById('va-screen-chart');
  const screenResultsEl = document.getElementById('va-screen-results');
  const binaryOutcomes = cohort.columns.filter(c => {
    const vals = cohort.rows.map(r => r[c]).filter(v => v !== null && v !== '' && v !== undefined).map(String);
    return vals.length >= 20 && new Set(vals).size === 2;
  });
  fill(anchorSel, preopNumeric);
  fill(screenOutcomeSel, binaryOutcomes);
  pick(anchorSel, ['smra','muscle_ra','muscle_attenuation'], 0);
  pick(screenOutcomeSel, ['major.complications','CRPOPF','CRPPH','DEATH 90d'], 0);

  if (!window.echarts) { note.textContent='ECharts could not be loaded. Check the server/browser internet connection.'; return; }
  const chart = echarts.init(chartEl);
  const palette = ['#64748b','#dc2626','#2563eb','#d97706','#7c3aed','#059669','#db2777','#0891b2'];

  function histogram(values, bins=16) {
    if (!values.length) return [];
    let min=Math.min(...values), max=Math.max(...values); if(min===max){min-=0.5;max+=0.5;}
    const width=(max-min)/bins, counts=Array(bins).fill(0);
    values.forEach(v => { let i=Math.floor((v-min)/width); if(i===bins)i--; counts[Math.max(0,Math.min(bins-1,i))]++; });
    return counts.map((count,i)=>[min+(i+0.5)*width,count,width]);
  }
  function render() {
    const x=xSel.value, y=ySel.value, outcome=outSel.value;
    const valid=cohort.rows.map((r,i)=>({r,i,x:Number(r[x]),y:Number(r[y])})).filter(d=>Number.isFinite(d.x)&&Number.isFinite(d.y));
    const categories=outcome ? [...new Set(valid.map(d=>d.r[outcome]).filter(v=>v!==null&&v!==''&&v!==undefined).map(String))].sort() : [];
    const series=[];
    const groups = outcome && categories.length ? categories : ['All patients'];
    groups.forEach((cat,idx)=>{
      const pts=valid.filter(d=>!outcome || String(d.r[outcome])===cat).map(d=>[d.x,d.y,d.i]);
      series.push({name:cat,type:'scatter',xAxisIndex:0,yAxisIndex:0,data:pts,symbolSize:8,itemStyle:{color:palette[idx%palette.length],opacity:.68},emphasis:{focus:'series',scale:1.6}});
    });
    const hx=histogram(valid.map(d=>d.x));
    const hy=histogram(valid.map(d=>d.y));
    series.push({name:'X distribution',type:'bar',xAxisIndex:1,yAxisIndex:1,data:hx.map(d=>[d[0],d[1]]),barWidth:'95%',silent:true,itemStyle:{color:'#cbd5e1'},tooltip:{show:false}});
    series.push({name:'Y distribution',type:'bar',xAxisIndex:2,yAxisIndex:2,data:hy.map(d=>[d[1],d[0]]),barWidth:'95%',silent:true,itemStyle:{color:'#cbd5e1'},tooltip:{show:false}});
    note.textContent = `${valid.length} of ${cohort.rows.length} patients have numeric values for both ${x} and ${y}.`;
    chart.setOption({
      animation:false,
      tooltip:{trigger:'item',formatter:p=>{ if(p.seriesType!=='scatter')return ''; const r=cohort.rows[p.data[2]]; const out=outcome?`<br>${outcome}: <b>${r[outcome] ?? '—'}</b>`:''; return `<b>Patient ${p.data[2]+1}</b><br>${x}: <b>${p.data[0]}</b><br>${y}: <b>${p.data[1]}</b>${out}`; }},
      legend:{type:'scroll',top:0,data:groups},
      grid:[{left:72,right:'22%',top:'24%',bottom:58},{left:72,right:'22%',top:48,height:'12%'},{left:'81%',right:22,top:'24%',bottom:58}],
      xAxis:[
        {type:'value',gridIndex:0,name:x,nameLocation:'middle',nameGap:36,scale:true},
        {type:'value',gridIndex:1,scale:true,axisLabel:{show:false},axisTick:{show:false},splitLine:{show:false}},
        {type:'value',gridIndex:2,name:'Count',nameLocation:'middle',nameGap:28,splitLine:{show:false}}
      ],
      yAxis:[
        {type:'value',gridIndex:0,name:y,nameLocation:'middle',nameGap:52,scale:true},
        {type:'value',gridIndex:1,name:'Count',nameGap:36,splitLine:{show:false}},
        {type:'value',gridIndex:2,scale:true,axisLabel:{show:false},axisTick:{show:false},splitLine:{show:false}}
      ],
      series
    }, true);
  }
  function sigmoid(z) {
    const v = Math.max(-30, Math.min(30, z));
    return 1 / (1 + Math.exp(-v));
  }

  function fitLogistic(train, featureCount) {
    const means = Array(featureCount).fill(0), sds = Array(featureCount).fill(1);
    for (let j=0;j<featureCount;j++) {
      means[j] = train.reduce((a,d)=>a+d.x[j],0) / train.length;
      const variance = train.reduce((a,d)=>a+(d.x[j]-means[j])**2,0) / Math.max(1,train.length-1);
      sds[j] = Math.sqrt(variance) || 1;
    }
    const w = Array(featureCount + 1).fill(0);
    const lr = 0.12, lambda = 0.01;
    for (let iter=0; iter<300; iter++) {
      const g = Array(w.length).fill(0);
      train.forEach(d => {
        let z=w[0];
        for(let j=0;j<featureCount;j++) z += w[j+1]*((d.x[j]-means[j])/sds[j]);
        const e=sigmoid(z)-d.y;
        g[0]+=e;
        for(let j=0;j<featureCount;j++) g[j+1]+=e*((d.x[j]-means[j])/sds[j]);
      });
      w[0] -= lr*g[0]/train.length;
      for(let j=1;j<w.length;j++) w[j] -= lr*(g[j]/train.length + lambda*w[j]);
    }
    return d => {
      let z=w[0];
      for(let j=0;j<featureCount;j++) z += w[j+1]*((d.x[j]-means[j])/sds[j]);
      return sigmoid(z);
    };
  }

  function aucScore(items) {
    const sorted=[...items].sort((a,b)=>a.p-b.p);
    let rank=1, rankSumPos=0, nPos=0, nNeg=0;
    for(let i=0;i<sorted.length;) {
      let j=i+1; while(j<sorted.length && sorted[j].p===sorted[i].p) j++;
      const avgRank=(rank + (rank+(j-i)-1))/2;
      for(let k=i;k<j;k++) { if(sorted[k].y===1){rankSumPos+=avgRank;nPos++;} else nNeg++; }
      rank += j-i; i=j;
    }
    if(!nPos || !nNeg) return null;
    return (rankSumPos - nPos*(nPos+1)/2)/(nPos*nNeg);
  }

  function cvAuc(data, featureCount, folds=5) {
    const byClass=[data.filter(d=>d.y===0),data.filter(d=>d.y===1)];
    const foldOf=new Map();
    byClass.forEach(group=>group.forEach((d,i)=>foldOf.set(d.id,i%folds)));
    const predictions=[];
    for(let f=0;f<folds;f++) {
      const train=data.filter(d=>foldOf.get(d.id)!==f), test=data.filter(d=>foldOf.get(d.id)===f);
      if(!train.some(d=>d.y===0)||!train.some(d=>d.y===1)||!test.length) continue;
      const predict=fitLogistic(train,featureCount);
      test.forEach(d=>predictions.push({y:d.y,p:predict(d)}));
    }
    return aucScore(predictions);
  }

  function outcomeEncoding(column) {
    const values=cohort.rows.map(r=>r[column]).filter(v=>v!==null&&v!==''&&v!==undefined).map(String);
    const classes=[...new Set(values)].sort();
    if(classes.length!==2) return null;
    return {classes, encode:v => String(v)===classes[1] ? 1 : 0};
  }

  function screenCombinations() {
    const anchor=anchorSel.value, outcome=screenOutcomeSel.value;
    if(!anchor || !outcome) { screenNote.textContent='Select an anchor variable and binary outcome first.'; return; }
    const enc=outcomeEncoding(outcome);
    if(!enc) { screenNote.textContent='The selected outcome must contain exactly two non-missing classes.'; return; }
    screenButton.disabled=true; screenButton.textContent='Screening…';
    screenNote.textContent=`Testing ${anchor} with ${Math.max(0, preopNumeric.length - 1)} configured preoperative numeric candidates using 5-fold cross-validated logistic regression…`;
    setTimeout(()=>{
      const results=[];
      preopNumeric.filter(c=>c!==anchor && c!==outcome).forEach(candidate=>{
        const data=[];
        cohort.rows.forEach((r,id)=>{
          const a=Number(r[anchor]), b=Number(r[candidate]), raw=r[outcome];
          if(Number.isFinite(a)&&Number.isFinite(b)&&raw!==null&&raw!==''&&raw!==undefined) data.push({id,x:[a,b],y:enc.encode(raw)});
        });
        const n0=data.filter(d=>d.y===0).length, n1=data.length-n0;
        if(data.length<50 || Math.min(n0,n1)<10) return;
        // Baseline and pair are deliberately evaluated on the identical complete-case subset.
        const base=data.map(d=>({id:d.id,x:[d.x[0]],y:d.y}));
        const aucBase=cvAuc(base,1), aucPair=cvAuc(data,2);
        if(aucBase===null||aucPair===null) return;
        results.push({candidate,n:data.length,n0,n1,aucBase,aucPair,delta:aucPair-aucBase});
      });
      results.sort((a,b)=>b.delta-a.delta);
      renderScreenResults(results.slice(0,15),anchor,outcome,enc.classes);
      screenButton.disabled=false; screenButton.textContent='Find interesting combinations';
    },20);
  }

  let screenChart=null;
  function renderScreenResults(results,anchor,outcome,classes) {
    if(!results.length) {
      screenNote.textContent='No candidate variables had enough complete observations and outcome events for screening.';
      screenChartEl.hidden=true; screenResultsEl.hidden=true; return;
    }
    screenNote.textContent=`Top ${results.length} preoperative candidates. Positive ΔAUC means the candidate improved discrimination beyond ${anchor} on the same complete-case patients. Only configured preoperative variables were screened. Outcome classes: ${classes[0]} / ${classes[1]}.`;
    screenChartEl.hidden=false; screenResultsEl.hidden=false;
    if(!screenChart) screenChart=echarts.init(screenChartEl);
    const display=[...results].reverse();
    screenChart.setOption({
      animation:false,
      grid:{left:'24%',right:55,top:24,bottom:42},
      tooltip:{trigger:'axis',axisPointer:{type:'shadow'},formatter:params=>{const i=params[0].dataIndex,r=display[i];return `<b>${r.candidate}</b><br>ΔAUC: <b>${r.delta.toFixed(3)}</b><br>Pair CV AUC: ${r.aucPair.toFixed(3)}<br>Anchor CV AUC: ${r.aucBase.toFixed(3)}<br>N: ${r.n}`;}},
      xAxis:{type:'value',name:'Δ cross-validated AUC',nameLocation:'middle',nameGap:28,axisLabel:{formatter:v=>Number(v).toFixed(2)}},
      yAxis:{type:'category',data:display.map(r=>r.candidate),axisLabel:{width:150,overflow:'truncate'}},
      series:[{type:'bar',data:display.map(r=>r.delta),itemStyle:{color:p=>p.value>=0?'#2563eb':'#cbd5e1'},markLine:{silent:true,symbol:'none',lineStyle:{color:'#64748b'},data:[{xAxis:0}]}}]
    },true);
    const rows=results.slice(0,10).map((r,i)=>`<tr><td>${i+1}</td><td><b>${escapeHtml(r.candidate)}</b></td><td>${r.aucPair.toFixed(3)}</td><td>${r.delta>=0?'+':''}${r.delta.toFixed(3)}</td><td>${r.n}</td><td><button type="button" data-candidate="${escapeAttr(r.candidate)}">Show in plot</button></td></tr>`).join('');
    screenResultsEl.innerHTML=`<table><thead><tr><th>#</th><th>Candidate</th><th>CV AUC</th><th>ΔAUC</th><th>N</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
    screenResultsEl.querySelectorAll('button[data-candidate]').forEach(btn=>btn.addEventListener('click',()=>{
      xSel.value=anchor; ySel.value=btn.dataset.candidate; if([...outSel.options].some(o=>o.value===outcome)) outSel.value=outcome; render(); chartEl.scrollIntoView({behavior:'smooth',block:'center'});
    }));
  }
  function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function escapeAttr(s){return escapeHtml(s);}

  screenButton.addEventListener('click',screenCombinations);
  [xSel,ySel,outSel].forEach(el=>el.addEventListener('change',render));
  render();
  window.addEventListener('resize',()=>{chart.resize(); if(screenChart) screenChart.resize();});
})();
