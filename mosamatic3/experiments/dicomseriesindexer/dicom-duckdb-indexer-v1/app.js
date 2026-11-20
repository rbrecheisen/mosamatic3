import * as duckdb from "./assets/duckdb-browser-bundle.mjs";

const $=id=>document.getElementById(id);
const fmt=new Intl.NumberFormat("en-US");
const logEl=$("log");
let db=null,conn=null,worker=null,selected="",busy=false,scanning=false,paused=false;
let runStart=0,activeBefore=0,currentCount=0,discovered=0,lastQuery="",opChain=Promise.resolve();
let collections=[],unitsSinceCheckpoint=0;
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
  log("DuckDB-Wasm 1.32.0 opened in local OPFS. No cloud connection is needed.");
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
function renderTable(data,columns){
  const root=$("results");root.replaceChildren();
  if(!data.length){root.textContent="No matching rows.";return}
  const table=document.createElement("table"),head=document.createElement("thead"),hdr=document.createElement("tr");
  for(const col of columns){const th=document.createElement("th");th.textContent=col;hdr.append(th)}head.append(hdr);table.append(head);
  const body=document.createElement("tbody");
  for(const row of data){const tr=document.createElement("tr");for(const col of columns){const td=document.createElement("td");const v=row[col];td.textContent=v===null||v===undefined?"":String(v);td.title=td.textContent;tr.append(td)}body.append(tr)}
  table.append(body);root.append(table);
}
async function runSQL(){
  let query;try{query=checkSQL($("sql").value)}catch(e){alert(e.message);return}
  busy=true;setControls();$("query-info").textContent="Running query…";
  try{
    const t0=performance.now();
    const limited=`SELECT * FROM (${query}) AS preview_query LIMIT 200`;
    const result=await queue(()=>conn.query(limited));
    const data=rows(result),cols=result.schema.fields.map(f=>f.name);
    renderTable(data,cols);lastQuery=query;
    $("query-info").textContent=`${data.length} preview rows · ${(performance.now()-t0).toFixed(0)} ms · CSV exports complete query`;
  }catch(e){log("SQL error: "+e.message);$("query-info").textContent="SQL error: "+e.message}
  finally{busy=false;setControls()}
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
  $("backup").onclick=backupDB;$("restore").onclick=()=>$("restore-file").click();
  $("restore-file").onchange=e=>{const file=e.target.files?.[0];e.target.value="";restoreDB(file)};
  $("reset").onclick=resetCollection;
  $("persist").onclick=async()=>{try{const granted=await navigator.storage.persist();log(granted?"Storage persistence granted.":"Browser did not grant storage persistence; keep database backups.");await updateStorage()}catch(e){log(e.message)}};
  setInterval(()=>{if(scanning){const ms=Number(collections.find(c=>c.id===selected)?.elapsed_active_ms||0)+activeBefore+(paused?0:Date.now()-runStart);$("elapsed").textContent="Active time: "+humanSeconds(ms/1000);const speed=ms?currentCount/(ms/1000):0;$("speed").textContent=speed?speed.toFixed(1):"—";$("eta").textContent=speed&&discovered>currentCount?humanSeconds((discovered-currentCount)/speed):"—"}},2500);
}
attach();
initDB().catch(e=>{dbStatus("DuckDB failed to start");log("FATAL: "+e.stack);alert("DuckDB could not start. Use Chrome/Edge and launch with the provided local server script. Details are in the log.")});
