"use strict";
importScripts("./parser-core.js");

// Scanning and decompression stay in this worker. The main thread hands each
// bounded batch to DuckDB and acknowledges it before more images are parsed.
const BATCH_SIZE=250;
let active=false,paused=false,stopped=false,collectionId="",batch=[],requestSeq=0;
const pending=new Map();

function send(type,fields={}){self.postMessage({type,...fields})}
function rpc(type,fields={}){
  const id=++requestSeq;
  return new Promise((resolve,reject)=>{
    pending.set(id,{resolve,reject});
    send(type,{requestId:id,...fields});
  });
}
async function flush(){
  if(!batch.length)return;
  const rows=batch;batch=[];
  await rpc("batch",{records:rows});
}
async function pauseCheck(){
  if((paused||stopped)&&batch.length)await flush();
  if(paused&&!stopped){
    send("status",{stage:"Paused"});
    while(paused&&!stopped)await new Promise(resolve=>setTimeout(resolve,120));
    if(!stopped)send("status",{stage:"Indexing"});
  }
  if(stopped)throw new Error("STOPPED");
}
async function* units(dir,prefix=""){
  // Unit at *scan-folder*, not at top-level patient-folder granularity: a
  // collection with every patient nested under a common parent stays bounded.
  let looseFiles=0;const children=[];
  for await(const item of dir.values()){
    await pauseCheck();const path=prefix?prefix+"/"+item.name:item.name;
    if(item.kind==="directory")children.push({handle:item,path});
    else if(/\.zip$/i.test(item.name))yield {kind:"zip",handle:item,key:"zip:"+path,path};
    else if(candidateFile(item.name))looseFiles++;
  }
  if(looseFiles)yield {kind:"files",handle:dir,key:"dir:"+(prefix||"(root)"),path:prefix,count:looseFiles};
  for(const child of children)yield* units(child.handle,child.path);
}
async function candidateCount(root){
  let count=0,unitCount=0;
  for await(const unit of units(root)){
    await pauseCheck();unitCount++;
    if(unit.kind==="files")count+=unit.count;
    else if(unit.kind==="zip"){
      try{const blob=await unit.handle.getFile();for await(const _entry of zipEntries(blob))count++}
      catch(_){count++}
    }
    if(unitCount%5===0)send("discovery",{count,unitCount});
  }
  send("discovery",{count,unitCount});
  return count;
}
function value(f,k){return String(f[k]||"")}
function validPatientId(s){return !!s&&!/^(?:x{2,}|anon(?:ymous|ymi[sz]ed)?|unknown|n\/a|none|null)$/i.test(s.trim())}
function intValue(v){const n=Number(v);return Number.isFinite(n)?Math.trunc(n):null}
function fileRecord(key,unit,path,archive,fingerprint,parsed,error){
  const f=parsed?.fields||{},folder=folderIdentity(path),dicomPatient=value(f,"00100020").trim();
  const goodId=validPatientId(dicomPatient),resolved=goodId?dicomPatient:folder.patient;
  const scan=classifyScan(f,path),phase=estimatePhase(f,path),actual=actualAcquisition(f);
  const study=value(f,"0020000D"),series=value(f,"0020000E");
  const status=error||!study||!series?"error":"ok";
  return {
    collection_id:collectionId,unit_key:unit,file_key:key,source_path:path,source_archive:archive,
    series_folder_path:path.includes("/")?path.slice(0,path.lastIndexOf("/")):"(root)",
    source_fingerprint:fingerprint,source_kind:archive?"zip":"file",
    dicom_patient_id:dicomPatient,folder_patient_id:folder.patient,
    patient_id_resolved:resolved,patient_id_source:goodId?"dicom":resolved?(dicomPatient?"folder_dicom_placeholder":"folder"):"unavailable",
    followup_label:folder.followup,study_uid:study,study_id:value(f,"00200010"),
    study_date:datePart(f["00080020"]),study_time:timePart(f["00080030"]),
    series_uid:series,series_number:value(f,"00200011"),sop_uid:value(f,"00080018"),
    acquisition_datetime:acquisition(f),acq_ms:acquisitionMilliseconds(actual),
    bolus_start:timePart(f["00181042"]),series_description:value(f,"0008103E"),
    protocol_name:value(f,"00181030"),modality:value(f,"00080060"),
    image_type:value(f,"00080008"),slice_thickness_mm:value(f,"00180050"),
    spacing_mm:value(f,"00180088"),orientation:orientation(f["00200037"]),
    image_position:value(f,"00200032"),rows:intValue(f["00280010"]),columns:intValue(f["00280011"]),
    pixel_spacing_mm:value(f,"00280030"),number_of_frames:Math.max(1,Math.min(1000000,intValue(f["00280008"])||1)),
    contrast_agent:value(f,"00180010"),scan_type:scan.type,scan_type_evidence:scan.evidence,
    estimated_phase:phase.phase,phase_confidence:phase.confidence,phase_evidence:phase.evidence,
    status:status,error_message:error||(!study||!series?"Missing Study/Series Instance UID":""),
    warnings:(parsed?.warnings||[]).join("; ")
  };
}
async function processFile(key,unit,path,archive,fingerprint,parseSource,seen){
  await pauseCheck();if(seen.has(key))return;
  let parsed=null,error="";
  try{parsed=await parseSource();if(parsed.status==="invalid"||parsed.status==="unsupported")error=parsed.reason||parsed.status}
  catch(e){error=String(e?.message||e)}
  batch.push(fileRecord(key,unit,path,archive,fingerprint,parsed,error));
  if(batch.length>=BATCH_SIZE)await flush();
}
async function processItem(item,unitKey,seen){
  const blob=await item.handle.getFile(),fingerprint=blob.size+"|"+blob.lastModified;
  if(item.kind==="file"){
    await processFile("f|"+item.path,unitKey,item.path,"",fingerprint,()=>parseBlob(blob),seen);
  }else{
    try{
      for await(const e of zipEntries(blob)){
        const key="z|"+item.path+"|"+e.index+"|"+e.name,path=item.path+"!/"+e.name;
        await processFile(key,unitKey,path,item.path,fingerprint,
          async()=>parseStream(await zipEntryStream(blob,e)),seen);
      }
    }catch(e){
      const key="badzip|"+item.path;
      await processFile(key,unitKey,item.path,item.path,fingerprint,async()=>{throw e},seen);
    }
  }
}
async function run(root,name){
  if(active)return;
  active=true;paused=false;stopped=false;collectionId=name;batch=[];
  let stage="Complete";
  try{
    send("status",{stage:"Discovering"});
    const total=await candidateCount(root);
    await rpc("discovered",{total});
    send("status",{stage:"Indexing"});
    for await(const unit of units(root)){
      await pauseCheck();send("current",{path:unit.path||"(root)"});
      const fingerprint=unit.kind==="files"?"":
        await unit.handle.getFile().then(f=>f.size+"|"+f.lastModified);
      const state=await rpc("unit_open",{unit_key:unit.key,fingerprint});
      if(state.changed)throw new Error("Source changed since indexing: "+unit.path+". Re-index this collection.");
      if(state.done)continue;
      const seen=new Set(state.keys||[]);
      if(unit.kind==="files"){
        for await(const item of unit.handle.values()){
          if(item.kind==="file"&&!/\.zip$/i.test(item.name)&&candidateFile(item.name))
            await processItem({kind:"file",handle:item,path:(unit.path?unit.path+"/":"")+item.name},unit.key,seen);
        }
      }else await processItem(unit,unit.key,seen);
      await flush();
      await rpc("unit_done",{unit_key:unit.key,fingerprint});
    }
    await flush();
  }catch(e){
    stage=e.message==="STOPPED"?"Stopped":"Failed";
    if(stage==="Failed")send("log",{message:"ERROR: "+e.message});
    try{await flush()}catch(ex){send("log",{message:"Final batch failed: "+ex.message})}
  }finally{
    try{await rpc("finish",{stage})}catch(e){send("log",{message:"Could not finalize job: "+e.message})}
    send("finished",{stage});active=false;
  }
}
self.onmessage=e=>{
  const m=e.data||{};
  if(m.replyTo){const p=pending.get(m.replyTo);if(p){pending.delete(m.replyTo);m.error?p.reject(new Error(m.error)):p.resolve(m.result||{})}return}
  if(m.command==="pause")paused=true;
  if(m.command==="resume")paused=false;
  if(m.command==="stop"){stopped=true;paused=false}
  if(m.command==="start")run(m.root,m.collection_id).catch(error=>send("log",{message:String(error)}));
};
