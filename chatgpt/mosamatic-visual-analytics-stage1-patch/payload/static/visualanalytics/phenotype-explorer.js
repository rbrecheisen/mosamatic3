(() => {
  const dataNode = document.getElementById('va-cohort-data');
  const workspace = document.getElementById('va-workspace');
  if (!dataNode || !workspace) return;
  let cohort;
  try { cohort = JSON.parse(dataNode.textContent); } catch (_) { return; }
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
  [xSel,ySel,outSel].forEach(el=>el.addEventListener('change',render));
  render();
  window.addEventListener('resize',()=>chart.resize());
})();
