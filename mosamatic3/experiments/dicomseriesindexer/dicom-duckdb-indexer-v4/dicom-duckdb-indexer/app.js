import * as duckdb from "./assets/duckdb-browser-bundle.mjs";

const $=id=>document.getElementById(id);
const fmt=new Intl.NumberFormat("en-US");
const logEl=$("log");
let db=null,conn=null,worker=null,selected="",busy=false,scanning=false,paused=false;
let runStart=0,activeBefore=0,currentCount=0,discovered=0,lastQuery="",opChain=Promise.resolve();
let collections=[],unitsSinceCheckpoint=0;
const PAGE_SIZE=200;
const ROW_ID="__dicom_indexer_internal_row_number__";
const tableState={query:"",total:0,page:0,rows:[],columns:[],columnOrder:[],widths:{},sortColumn:"",sortDirection:"",selected:new Map()};
const dbPath="opfs://dicom_inventory.duckdb";
const dbFile="dicom_inventory.duckdb";
const q=s=>"'"+String(s).replaceAll("'","''")+"'";
const humanSeconds=n=>!Number.isFinite(n)||n<0?"—":n<60?Math.round(n)+"s":n<3600?Math.round(n/60)+"m":(n/3600).toFixed(1)+"h";
const queue=fn=>{const promise=opChain.then(fn);opChain=promise.catch(e=>{log("Database operation failed: "+e.message)});return promise};
function log(s){const time=new Date().toLocaleTimeString();logEl.textContent=`[${time}] ${s}\n`+logEl.textContent.slice(0,5400)}
function status(s){$("job-status").textContent=s}
function dbStatus(s){$("db-status").textContent=s}
function accountActive(){if(!paused&&scanning){activeBefore+=Math.max(0,Date.now()-runStart);runStart=Date.now()}}
function setControls(){const ready=!!conn&&!busy,chosen=!!selected;
  $("create").disabled=!ready||scanning;$("pick").disabled=!ready||scanning||!chosen;
  $("pause").disabled=!scanning||paused;$("resume").disabled=!scanning||!paused;$("stop").disabled=!scanning;
  $("run").disabled=!ready;$("export").disabled=!ready;$("backup").disabled=!ready||scanning;
  $("restore").disabled=!ready||scanning;$("reset").disabled=!ready||scanning||!chosen;
  $("example").disabled=!ready;$("persist").disabled=!ready;
  $("refresh").disabled=!ready||scanning;$("collections").disabled=!ready||scanning;
  updateTableControls();
}
function updateTableControls(){
  const ready=!!conn&&!busy,total=tableState.total,selectedCount=tableState.selected.size;
  $("prev-page").disabled=!ready||!tableState.query||tableState.page===0;
  $("next-page").disabled=!ready||!tableState.query||(tableState.page+1)*PAGE_SIZE>=total;
  $("page-label").textContent=tableState.query?`Page ${tableState.page+1} of ${Math.max(1,Math.ceil(total/PAGE_SIZE))} · ${fmt.format(total)} rows`:"No results yet";
  $("export-selected").disabled=!ready||selectedCount===0;
  $("export-selected").textContent=`Export selected rows to CSV (${fmt.format(selectedCount)})`;
  $("clear-selection").disabled=!ready||selectedCount===0;
  $("selection-info").textContent=`${fmt.format(selectedCount)} ${selectedCount===1?"row":"rows"} selected`;
}
function rows(table){return table.toArray().map(r=>r.toJSON())}
async function initDB(){
  dbStatus("Loading offline DuckDB-Wasm…");
  const engine=new Worker(new URL("./assets/duckdb-browser-eh.worker.js",import.meta.url));
  db=new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.ERROR),engine);
  await db.instantiate(new URL("./assets/duckdb-eh.wasm",import.meta.url).href);
  await db.open({path:dbPath,accessMode:duckdb.DuckDBAccessMode.READ_WRITE});
  conn=await db.connect();
  const schema=await (await fetch("./schema.sql")).text();
  for(const statement of schema.split(/;\s*(?:\r?\n|$)/).map(s=>s.trim()).filter(Boolean))await conn.query(statement);
  dbStatus("Persistent DuckDB ready");
  await updateStorage();
  await refreshCollections();
  setControls();
  log("DICOM Indexer v1.1.2 · DuckDB-Wasm 1.32.0 opened in local OPFS. No cloud connection is needed.");
}
async function updateStorage(){
  if(!navigator.storage?.estimate)return;
  const {usage=0,quota=0}=await navigator.storage.estimate();
  const durable=await navigator.storage.persisted?.();
  $("storage").textContent=`Browser storage: ${(usage/1048576).toFixed(1)} MiB used / ${(quota/1073741824).toFixed(1)} GiB quota · ${durable?"durable":"evictable"}`;
}
async function refreshCollections(){
  if(!conn)return;
  collections=rows(await conn.query("SELECT id,name,root_name,status,discovered_count,processed_count,elapsed_active_ms FROM collections ORDER BY created_at DESC"));
  if(!collections.some(c=>c.id===selected))selected=collections[0]?.id||"";
  const select=$("collections");select.replaceChildren();
  if(!collections.length){const o=new Option("Create a collection first","");select.add(o)}
  else for(const c of collections){const o=new Option(`${c.name} · ${c.status} · ${c.root_name}`,c.id);select.add(o)}
  select.value=selected;
  await updateMetrics();
  loadExample();setControls();
}
async function updateMetrics(){
  const c=collections.find(c=>c.id===selected);
  currentCount=Number(c?.processed_count||0);discovered=Number(c?.discovered_count||0);
  $("processed").textContent=fmt.format(currentCount);$("discovered").textContent=discovered?fmt.format(discovered):"—";
  const ms=Number(c?.elapsed_active_ms||0)+activeBefore+(scanning&&!paused?Date.now()-runStart:0);
  const speed=ms?currentCount/(ms/1000):0;
  $("speed").textContent=speed?speed.toFixed(1):"—";
  $("elapsed").textContent=ms?"Active time: "+humanSeconds(ms/1000):"";
  $("eta").textContent=speed&&discovered>currentCount?humanSeconds((discovered-currentCount)/speed):"—";
  $("progress").value=discovered?Math.min(100,100*currentCount/discovered):0;
  status(scanning?(paused?"Paused":"Indexing"):c?.status||"Idle");
  if(!selected){for(const id of ["series","studies","duplicates","errors"])$(id).textContent="—";return}
  try{
    const r=rows(await conn.query(`SELECT
       (SELECT COUNT(*) FROM dicom_series WHERE collection_id=${q(selected)}) AS series,
       (SELECT COUNT(*) FROM dicom_studies WHERE collection_id=${q(selected)}) AS studies,
       (SELECT COALESCE(SUM(number_of_copies-1),0) FROM duplicate_sources WHERE collection_id=${q(selected)}) AS duplicates,
       (SELECT COUNT(*) FROM dicom_files WHERE collection_id=${q(selected)} AND status <> 'ok') AS errors`))[0];
    for(const id of ["series","studies","duplicates","errors"])$(id).textContent=fmt.format(Number(r[id]||0));
  }catch(e){log("Metrics: "+e.message)}
}
async function createCollection(){
  const name=$("collection-name").value.trim();if(!name){alert("Enter a collection name.");return}
  let root;
  try{root=await window.showDirectoryPicker({mode:"read",id:"dicom-inventory"})}
  catch(e){if(e.name!=="AbortError")log("Choose root: "+e.message);return}
  const id=crypto.randomUUID();
  await queue(async()=>{
    await conn.query(`INSERT INTO collections (id,name,root_name,status) VALUES (${q(id)},${q(name)},${q(root.name)},'New')`);
    selected=id;$("collection-name").value="";await refreshCollections();
  });
  log(`Collection '${name}' created. Root: ${root.name}`);
  await startWorker(root);
}
async function chooseRoot(){
  const coll=collections.find(c=>c.id===selected);if(!coll)return;
  let root;
  try{root=await window.showDirectoryPicker({mode:"read",id:"dicom-inventory"})}
  catch(e){if(e.name!=="AbortError")log("Folder selection failed: "+e.message);return}
  if(root.name!==coll.root_name){alert(`Incorrect root folder. Expected '${coll.root_name}', selected '${root.name}'.`);return}
  await startWorker(root);
}
async function startWorker(root){
  if(scanning)return;
  worker=new Worker("./scanner-worker.js");scanning=true;paused=false;runStart=Date.now();activeBefore=0;setControls();
  $("current").textContent="Discovering DICOM and ZIP candidates…";
  log(`Started indexing ${root.name}. Existing batches and completed units will be skipped.`);
  worker.onmessage=event=>onWorkerMessage(event.data);
  worker.onerror=e=>{log("Scanner worker error: "+e.message);status("Worker error");};
  worker.postMessage({command:"start",root,collection_id:selected});
}
async function onWorkerMessage(m){
  if(m.requestId){
    try{const result=await queue(()=>handleRpc(m));worker?.postMessage({replyTo:m.requestId,result:result||{}})}
    catch(e){worker?.postMessage({replyTo:m.requestId,error:String(e.message||e)});log("Worker storage error: "+e.message)}
    return;
  }
  if(m.type==="status")status(m.stage);
  if(m.type==="current")$("current").textContent="Current: "+m.path;
  if(m.type==="discovery"){$("discovered").textContent=fmt.format(m.count);status(`Discovering (${fmt.format(m.unitCount)} root units)`)}
  if(m.type==="log")log(m.message);
  if(m.type==="finished"){
    scanning=false;paused=false;worker?.terminate();worker=null;
    log(`Indexing ended: ${m.stage}.`);status(m.stage);setControls();
    await queue(refreshCollections);
  }
}
async function handleRpc(m){
  const id=q(selected);
  if(m.type==="discovered"){
    discovered=m.total;
    await conn.query(`UPDATE collections SET discovered_count=${Math.trunc(m.total)},status='Indexing' WHERE id=${id}`);
    return {};
  }
  if(m.type==="unit_open"){
    const rec=rows(await conn.query(`SELECT fingerprint,completed FROM scan_units WHERE collection_id=${id} AND unit_key=${q(m.unit_key)}`))[0];
    const changed=!!rec&&!!rec.fingerprint&&!!m.fingerprint&&rec.fingerprint!==m.fingerprint;
    if(rec?.completed||changed)return {done:!!rec?.completed,changed,keys:[]};
    const keys=rows(await conn.query(`SELECT file_key FROM dicom_files WHERE collection_id=${id} AND unit_key=${q(m.unit_key)}`)).map(r=>r.file_key);
    return {done:false,changed:false,keys};
  }
  if(m.type==="batch"){
    if(!m.records?.length)return {};
    const name="batch_"+crypto.randomUUID().replaceAll("-","")+".ndjson";
    const ndjson=m.records.map(r=>JSON.stringify(r)).join("\n")+"\n";
    await db.registerFileText(name,ndjson);
    let elapsed=0;
    try{
      await conn.query("BEGIN TRANSACTION");
      try{
        await conn.query(`INSERT INTO dicom_files BY NAME SELECT * FROM read_json_auto(${q(name)}, format='newline_delimited') ON CONFLICT DO NOTHING`);
        accountActive();elapsed=activeBefore;activeBefore=0;
        await conn.query(`UPDATE collections SET processed_count=(SELECT COUNT(*) FROM dicom_files WHERE collection_id=${id}),elapsed_active_ms=elapsed_active_ms+${Math.max(0,elapsed)},status='Indexing' WHERE id=${id}`);
        await conn.query("COMMIT");
      }catch(e){await conn.query("ROLLBACK");throw e}
    }finally{await db.dropFile(name)}
    const c=collections.find(x=>x.id===selected);if(c){c.processed_count=(Number(c.processed_count)||0)+m.records.length;c.elapsed_active_ms=(Number(c.elapsed_active_ms)||0)+elapsed}
    currentCount+=m.records.length;
    $("processed").textContent=fmt.format(currentCount);$("progress").value=discovered?100*currentCount/discovered:0;
    return {};
  }
  if(m.type==="unit_done"){
    await conn.query(`INSERT INTO scan_units VALUES (${id},${q(m.unit_key)},${q(m.fingerprint)},TRUE)
      ON CONFLICT (collection_id,unit_key) DO UPDATE SET fingerprint=excluded.fingerprint,completed=TRUE`);
    if(++unitsSinceCheckpoint>=25){await conn.query("CHECKPOINT");unitsSinceCheckpoint=0}
    return {};
  }
  if(m.type==="finish"){
    accountActive();const elapsed=activeBefore;activeBefore=0;
    await conn.query(`UPDATE collections SET status=${q(m.stage)},finished_at=CURRENT_TIMESTAMP,elapsed_active_ms=elapsed_active_ms+${Math.max(0,elapsed)},processed_count=(SELECT COUNT(*) FROM dicom_files WHERE collection_id=${id}) WHERE id=${id}`);
    await conn.query("CHECKPOINT");unitsSinceCheckpoint=0;return {};
  }
  return {};
}
function loadExample(){
  const id=selected?q(selected):"''";
  const sql={
    series:`SELECT patient_id,followup_label,study_id,study_date,series_number,series_description,scan_type,scan_types_present,estimated_phase,postcontrast_delay_seconds,number_of_instances,number_of_frames,orientation,rows,columns,series_folder_path,source_archive FROM dicom_series WHERE collection_id=${id} ORDER BY patient_id,study_date,series_number`,
    axial:`SELECT * FROM dicom_series WHERE collection_id=${id} AND axial_ct_candidate='yes' ORDER BY patient_id,study_date`,
    venous:`SELECT patient_id,study_date,series_description,series_folder_path,source_archive,postcontrast_delay_seconds,number_of_instances FROM dicom_series WHERE collection_id=${id} AND axial_ct_candidate='yes' AND estimated_phase='portal_venous' ORDER BY patient_id,study_date`,
    duplicates:`SELECT * FROM duplicate_sources WHERE collection_id=${id} ORDER BY number_of_copies DESC`,
    studies:`SELECT * FROM dicom_studies WHERE collection_id=${id} ORDER BY patient_id_resolved,study_date`,
    files:`SELECT patient_id_resolved,study_uid,series_uid,sop_uid,source_path,scan_type,status FROM dicom_files WHERE collection_id=${id} ORDER BY source_path`,
    performance:`SELECT name,root_name,status,processed_count,discovered_count,ROUND(processed_count/NULLIF(elapsed_active_ms/1000,0),1) AS files_per_second,ROUND(elapsed_active_ms/1000,1) AS active_seconds FROM collections ORDER BY created_at DESC`
  };
  $("sql").value=sql[$("examples").value]||sql.series;
}
function checkSQL(query){
  const cleaned=query.trim().replace(/;\s*$/g,"");
  if(!/^(?:SELECT|WITH|EXPLAIN)\b/i.test(cleaned)||/;/.test(cleaned))throw new Error("The SQL workspace only permits one SELECT / WITH / EXPLAIN statement. Use collection reset for destructive changes.");
  return cleaned;
}
function csvVal(v){
  let s=v===null||v===undefined?"":typeof v==="bigint"?v.toString():v instanceof Date?v.toISOString():String(v);
  // Prevent Excel/LibreOffice from executing formulas embedded in source paths.
  if(/^[\s]*[=+@-]/.test(s)&&!/^[-+]\d+(?:\.\d+)?$/.test(s))s="'"+s;
  return /[",\n\r]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;
}
function sqlIdentifier(name){return '"'+String(name).replaceAll('"','""')+'"'}
function columnWidth(name){return tableState.widths[name]||Math.min(380,Math.max(125,name.length*8+34))}
function tablePixelWidth(){return 39+tableState.columnOrder.reduce((n,col)=>n+columnWidth(col),0)}
function rowSnapshot(row){return Object.fromEntries(tableState.columns.map(c=>[c,row[c]]))}
function selectPage(checked){
  for(const item of tableState.rows){
    if(checked)tableState.selected.set(item.key,rowSnapshot(item.data));
    else tableState.selected.delete(item.key);
  }
  renderTable();updateTableControls();
}
function renderTable(){
  const root=$("results"),left=root.scrollLeft,top=root.scrollTop;
  root.replaceChildren();
  if(!tableState.rows.length){root.textContent="No matching rows on this page.";updateTableControls();return}
  const table=document.createElement("table");table.style.width=tablePixelWidth()+"px";
  const colgroup=document.createElement("colgroup"),selectorCol=document.createElement("col");
  selectorCol.style.width="39px";colgroup.append(selectorCol);
  const widthCols=new Map();
  for(const name of tableState.columnOrder){const col=document.createElement("col");col.style.width=columnWidth(name)+"px";widthCols.set(name,col);colgroup.append(col)}
  table.append(colgroup);
  const head=document.createElement("thead"),hdr=document.createElement("tr");
  const selectAllTh=document.createElement("th");selectAllTh.className="selector-cell head";
  const selectAll=document.createElement("input");selectAll.type="checkbox";selectAll.setAttribute("aria-label","Select all rows on this page");
  const checked=tableState.rows.filter(r=>tableState.selected.has(r.key)).length;
  selectAll.checked=checked===tableState.rows.length;
  selectAll.indeterminate=checked>0&&checked<tableState.rows.length;
  selectAll.onchange=()=>selectPage(selectAll.checked);
  selectAllTh.append(selectAll);hdr.append(selectAllTh);
  for(const name of tableState.columnOrder){
    const th=document.createElement("th");th.className="data-header";th.draggable=true;
    th.dataset.column=name;th.title="Click to sort · drag to reorder · drag right edge to resize";
    th.setAttribute("aria-sort",tableState.sortColumn===name?(tableState.sortDirection==="ASC"?"ascending":"descending"):"none");
    const label=document.createElement("span");label.textContent=name;th.append(label);
    if(tableState.sortColumn===name){const arrow=document.createElement("span");arrow.className="sort-arrow";arrow.textContent=tableState.sortDirection==="ASC"?"▲":"▼";th.append(arrow)}
    th.addEventListener("click",()=>sortResults(name));
    th.addEventListener("dragstart",event=>{event.dataTransfer.effectAllowed="move";event.dataTransfer.setData("text/plain",name)});
    th.addEventListener("dragover",event=>{event.preventDefault();event.dataTransfer.dropEffect="move";th.classList.add("drag-over")});
    th.addEventListener("dragleave",()=>th.classList.remove("drag-over"));
    th.addEventListener("drop",event=>{
      event.preventDefault();th.classList.remove("drag-over");
      const source=event.dataTransfer.getData("text/plain");if(source===name||!tableState.columnOrder.includes(source))return;
      const order=tableState.columnOrder;order.splice(order.indexOf(source),1);order.splice(order.indexOf(name),0,source);
      renderTable();
    });
    const handle=document.createElement("span");handle.className="col-resize";handle.title="Drag to resize column";
    handle.addEventListener("click",e=>e.stopPropagation());
    handle.addEventListener("pointerdown",event=>{
      event.preventDefault();event.stopPropagation();th.draggable=false;
      const initial=columnWidth(name),x=event.clientX;
      handle.setPointerCapture(event.pointerId);
      const move=e=>{
        const width=Math.max(65,Math.min(850,initial+e.clientX-x));
        tableState.widths[name]=width;widthCols.get(name).style.width=width+"px";
        table.style.width=tablePixelWidth()+"px";
      };
      const finish=()=>{handle.removeEventListener("pointermove",move);handle.removeEventListener("pointerup",finish);handle.removeEventListener("pointercancel",finish);th.draggable=true};
      handle.addEventListener("pointermove",move);handle.addEventListener("pointerup",finish);handle.addEventListener("pointercancel",finish);
    });
    th.append(handle);hdr.append(th);
  }
  head.append(hdr);table.append(head);
  const body=document.createElement("tbody");
  for(const item of tableState.rows){
    const tr=document.createElement("tr"),selected=tableState.selected.has(item.key);
    tr.classList.toggle("selected-row",selected);
    const cell=document.createElement("td");cell.className="selector-cell";
    const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.checked=selected;
    checkbox.setAttribute("aria-label","Select row "+item.key);
    checkbox.onchange=()=>{
      if(checkbox.checked)tableState.selected.set(item.key,rowSnapshot(item.data));
      else tableState.selected.delete(item.key);
      tr.classList.toggle("selected-row",checkbox.checked);
      const checkedCount=tableState.rows.filter(r=>tableState.selected.has(r.key)).length;
      selectAll.checked=checkedCount===tableState.rows.length;
      selectAll.indeterminate=checkedCount>0&&checkedCount<tableState.rows.length;
      updateTableControls();
    };
    cell.append(checkbox);tr.append(cell);
    for(const name of tableState.columnOrder){
      const td=document.createElement("td"),value=item.data[name];
      td.textContent=value===null||value===undefined?"":String(value);
      td.title=td.textContent;tr.append(td);
    }
    body.append(tr);
  }
  table.append(body);root.append(table);root.scrollLeft=left;root.scrollTop=top;
  updateTableControls();
}
async function loadPage(page){
  if(!tableState.query)return;
  const indexed=`SELECT ROW_NUMBER() OVER () AS ${sqlIdentifier(ROW_ID)}, * FROM (${tableState.query}) AS source_query`;
  const order=tableState.sortColumn?`${sqlIdentifier(tableState.sortColumn)} ${tableState.sortDirection} NULLS LAST, ${sqlIdentifier(ROW_ID)}`:sqlIdentifier(ROW_ID);
  const sql=`SELECT * FROM (${indexed}) AS numbered_query ORDER BY ${order} LIMIT ${PAGE_SIZE} OFFSET ${page*PAGE_SIZE}`;
  const result=await queue(()=>conn.query(sql));
  const names=result.schema.fields.map(f=>f.name).filter(name=>name!==ROW_ID);
  if(!tableState.columns.length){tableState.columns=names;tableState.columnOrder=[...names];tableState.widths={}}
  tableState.page=page;
  tableState.rows=rows(result).map(data=>({key:String(data[ROW_ID]),data}));
  renderTable();
  $("query-info").textContent=`Showing ${fmt.format(tableState.rows.length)} of ${fmt.format(tableState.total)} rows · Sorting applies to the full result`;
}
async function changePage(page){
  if(busy||page<0||page*PAGE_SIZE>=tableState.total)return;
  busy=true;setControls();
  try{await loadPage(page)}catch(e){log("Page error: "+e.message);$("query-info").textContent="Page error: "+e.message}
  finally{busy=false;setControls()}
}
async function sortResults(name){
  if(busy||!tableState.query)return;
  const prior=[tableState.sortColumn,tableState.sortDirection];
  tableState.sortDirection=prior[0]===name&&prior[1]==="ASC"?"DESC":"ASC";
  tableState.sortColumn=name;
  try{await changePage(0)}catch(e){[tableState.sortColumn,tableState.sortDirection]=prior;log(e.message)}
}
async function runSQL(){
  let query;try{query=checkSQL($("sql").value)}catch(e){alert(e.message);return}
  busy=true;setControls();$("query-info").textContent="Running query…";
  try{
    const start=performance.now();
    const result=await queue(()=>conn.query(`SELECT COUNT(*) AS count FROM (${query}) AS count_query`));
    const total=Number(rows(result)[0]?.count||0);
    if(query!==tableState.query){
      tableState.selected.clear();tableState.columns=[];tableState.columnOrder=[];tableState.widths={};
      tableState.sortColumn="";tableState.sortDirection="";
    }
    tableState.query=query;tableState.total=total;lastQuery=query;
    await loadPage(0);
    $("query-info").textContent=`${fmt.format(total)} matching rows · ${(performance.now()-start).toFixed(0)} ms · Browse in pages of ${PAGE_SIZE}`;
  }catch(e){log("SQL error: "+e.message);$("query-info").textContent="SQL error: "+e.message}
  finally{busy=false;setControls()}
}
function exportSelectedRows(){
  if(!tableState.selected.size)return;
  const names=tableState.columnOrder;
  const records=[...tableState.selected.entries()].sort(([a],[b])=>BigInt(a)<BigInt(b)?-1:BigInt(a)>BigInt(b)?1:0);
  const lines=[names.map(csvVal).join(",")];
  for(const [,record] of records)lines.push(names.map(name=>csvVal(record[name])).join(","));
  const blob=new Blob(["\ufeff",lines.join("\r\n"),"\r\n"],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="dicom_inventory_selected_rows.csv";a.click();
  setTimeout(()=>URL.revokeObjectURL(url),20000);
  $("query-info").textContent=`Exported ${fmt.format(records.length)} selected rows. Column order matches the displayed table.`;
}
async function exportQuery(){
  let query;try{query=checkSQL($("sql").value)}catch(e){alert(e.message);return}
  let destination=null;
  if(window.showSaveFilePicker){try{const handle=await showSaveFilePicker({suggestedName:"dicom_inventory_query.csv",types:[{description:"CSV",accept:{"text/csv":[".csv"]}}]});destination=await handle.createWritable()}
    catch(e){if(e.name==="AbortError")return;log("File save picker failed; using browser download: "+e.message)}}
  busy=true;setControls();$("query-info").textContent="Exporting query…";
  const chunks=[];let count=0;
  try{
    await queue(async()=>{
      const reader=await conn.send(query,true);let first=true;
      for await(const batch of reader){
        if(first){const header=batch.schema.fields.map(f=>f.name).map(csvVal).join(",")+"\r\n";
          if(destination)await destination.write("\ufeff"+header);else chunks.push("\ufeff"+header);first=false}
        const names=batch.schema.fields.map(f=>f.name);
        const chunk=Array.from(batch,row=>names.map(n=>csvVal(row.toJSON()[n])).join(",")).join("\r\n");
        if(destination)await destination.write(chunk+"\r\n");else chunks.push(chunk+"\r\n");
        count+=batch.numRows;
        $("query-info").textContent=`Exporting ${fmt.format(count)} rows…`;
      }
    });
    if(destination)await destination.close();else{
      const url=URL.createObjectURL(new Blob(chunks,{type:"text/csv;charset=utf-8"}));
      const a=document.createElement("a");a.href=url;a.download="dicom_inventory_query.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),20000);
    }
    $("query-info").textContent=`Exported ${fmt.format(count)} rows.`;
  }catch(e){if(destination)await destination.abort().catch(()=>{});log("CSV export failed: "+e.message);$("query-info").textContent="Export failed: "+e.message}
  finally{busy=false;setControls()}
}
async function shutdownDB(){
  if(conn){await conn.query("CHECKPOINT");await conn.close();conn=null}
  if(db){await db.terminate();db=null}
}
async function backupDB(){
  busy=true;setControls();dbStatus("Preparing database backup…");
  try{
    await shutdownDB();
    const opfs=await navigator.storage.getDirectory(),file=await (await opfs.getFileHandle(dbFile)).getFile();
    const url=URL.createObjectURL(file),a=document.createElement("a");a.href=url;a.download=`dicom_inventory_${new Date().toISOString().slice(0,10)}.duckdb`;a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
    log(`Database backup prepared (${(file.size/1048576).toFixed(1)} MiB).`);
  }catch(e){log("Backup failed: "+e.message);alert("Backup failed: "+e.message)}
  finally{try{await initDB()}catch(e){dbStatus("Reopen failed: "+e.message)}busy=false;setControls()}
}
async function restoreDB(file){
  if(!file)return;
  if(!confirm("Replace all locally indexed collections with the selected DuckDB backup? This cannot be undone unless you already have a backup."))return;
  busy=true;setControls();dbStatus("Restoring backup…");
  try{
    await shutdownDB();
    const opfs=await navigator.storage.getDirectory(),handle=await opfs.getFileHandle(dbFile,{create:true});
    const writer=await handle.createWritable();await writer.write(file);await writer.close();
    log(`Restored database backup ${file.name} (${(file.size/1048576).toFixed(1)} MiB).`);
  }catch(e){log("Restore failed: "+e.message);alert("Restore failed: "+e.message)}
  finally{try{selected="";await initDB()}catch(e){dbStatus("Reopen failed: "+e.message)}busy=false;setControls()}
}
async function resetCollection(){
  const c=collections.find(x=>x.id===selected);if(!c||!confirm(`Delete all indexed metadata and progress for '${c.name}'? This does not delete any DICOM files.`))return;
  await queue(async()=>{
    await conn.query("BEGIN TRANSACTION");
    try{for(const table of ["dicom_files","scan_units","collections"])await conn.query(`DELETE FROM ${table} WHERE ${table==="collections"?"id":"collection_id"}=${q(selected)}`);await conn.query("COMMIT")}
    catch(e){await conn.query("ROLLBACK");throw e}
    await conn.query("CHECKPOINT");selected="";await refreshCollections();
  });
  log(`Removed local metadata for ${c.name}.`);
}
function attach(){
  $("collections").onchange=()=>{selected=$("collections").value;queue(async()=>{await updateMetrics();loadExample()})};
  $("create").onclick=createCollection;$("pick").onclick=chooseRoot;
  $("pause").onclick=()=>{if(scanning&&!paused){accountActive();paused=true;worker.postMessage({command:"pause"});log("Pause requested (finishes current batch first).");setControls()}};
  $("resume").onclick=()=>{if(scanning&&paused){paused=false;runStart=Date.now();worker.postMessage({command:"resume"});log("Resumed.");setControls()}};
  $("stop").onclick=()=>{if(scanning){worker.postMessage({command:"stop"});log("Stop requested (committing pending records).")}};
  $("refresh").onclick=()=>queue(refreshCollections);$("example").onclick=loadExample;
  $("run").onclick=runSQL;$("export").onclick=exportQuery;
  $("export-selected").onclick=exportSelectedRows;
  $("prev-page").onclick=()=>changePage(tableState.page-1);
  $("next-page").onclick=()=>changePage(tableState.page+1);
  $("clear-selection").onclick=()=>{tableState.selected.clear();renderTable();updateTableControls()};
  $("backup").onclick=backupDB;$("restore").onclick=()=>$("restore-file").click();
  $("restore-file").onchange=e=>{const file=e.target.files?.[0];e.target.value="";restoreDB(file)};
  $("reset").onclick=resetCollection;
  $("persist").onclick=async()=>{try{const granted=await navigator.storage.persist();log(granted?"Storage persistence granted.":"Browser did not grant storage persistence; keep database backups.");await updateStorage()}catch(e){log(e.message)}};
  setInterval(()=>{if(scanning){const ms=Number(collections.find(c=>c.id===selected)?.elapsed_active_ms||0)+activeBefore+(paused?0:Date.now()-runStart);$("elapsed").textContent="Active time: "+humanSeconds(ms/1000);const speed=ms?currentCount/(ms/1000):0;$("speed").textContent=speed?speed.toFixed(1):"—";$("eta").textContent=speed&&discovered>currentCount?humanSeconds((discovered-currentCount)/speed):"—"}},2500);
}
attach();
initDB().catch(e=>{dbStatus("DuckDB failed to start");log("FATAL: "+e.stack);alert("DuckDB could not start. Use Chrome/Edge and launch with the provided local server script. Details are in the log.")});
