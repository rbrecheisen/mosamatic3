"use strict";
// DICOM and ZIP metadata parser, sourced from the previous standalone indexer.
// Keep the same header-read ceiling as the original standalone parser.
const HEADER_LIMIT=12*1024*1024;
const decoder=new TextDecoder("utf-8");
const wanted=new Set(["00100020","0020000D","00200010","00080008","00080020","00080030","0008002A","00080022","00080032","00080021","00080031","0020000E","00200011","0008103E","00181030","00080060","00180050","00180088","00200037","00200032","00280010","00280011","00280030","00180010","00181042","00080018","00280008","00189074"]);
function lowerExt(name){return name.toLowerCase()}
function candidateFile(name){const n=lowerExt(name);if(/\.(zip|7z|rar|tar|gz|png|jpg|jpeg|gif|pdf|csv|xlsx?|txt|json|xml|html?|js|md|log|db|ini|exe|ds_store)$/i.test(n))return false;return true}
async function* walk(dir,prefix){for await(const item of dir.values()){await pauseCheck();const path=prefix?prefix+"/"+item.name:item.name;if(item.kind==="directory")yield* walk(item,path);else if(/\.zip$/i.test(item.name))yield{kind:"zip",handle:item,path:path};else if(candidateFile(item.name))yield{kind:"file",handle:item,path:path}}}

const u16=(b,o)=>new DataView(b.buffer,b.byteOffset,b.byteLength).getUint16(o,true);
const u32=(b,o)=>new DataView(b.buffer,b.byteOffset,b.byteLength).getUint32(o,true);
function largeNum(view,off){const n=view.getBigUint64(off,true);if(n>BigInt(Number.MAX_SAFE_INTEGER))throw new Error("ZIP offset exceeds safe JavaScript integer");return Number(n)}
async function range(blob,start,end){return new Uint8Array(await blob.slice(start,end).arrayBuffer())}
async function zipInfo(blob){
  const tail=await range(blob,Math.max(0,blob.size-66000),blob.size),base=blob.size-tail.length;
  let p=-1;for(let i=tail.length-22;i>=0;i--){if(u32(tail,i)===0x06054b50&&i+22+u16(tail,i+20)<=tail.length){p=i;break}}
  if(p<0)throw new Error("ZIP end-of-central-directory not found");
  let count=u16(tail,p+10),size=u32(tail,p+12),offset=u32(tail,p+16);
  if(u16(tail,p+4)!==0||u16(tail,p+6)!==0)throw new Error("Multipart ZIP archives are not supported");
  if(count===65535||size===0xffffffff||offset===0xffffffff){
    const locator=await range(blob,base+p-20,base+p);
    if(locator.length!==20||u32(locator,0)!==0x07064b50)throw new Error("Invalid ZIP64 locator");
    const view=new DataView(locator.buffer,locator.byteOffset,locator.byteLength);
    const zoff=largeNum(view,8),rec=await range(blob,zoff,zoff+56);
    if(u32(rec,0)!==0x06064b50)throw new Error("Invalid ZIP64 record");
    const v=new DataView(rec.buffer,rec.byteOffset,rec.byteLength);
    count=largeNum(v,32);size=largeNum(v,40);offset=largeNum(v,48);
  }
  if(offset+size>blob.size)throw new Error("ZIP central directory points beyond file");
  return {count:count,size:size,offset:offset}
}
function extraZip64(extra,rawUncomp,rawComp,rawOffset){
  let uncomp=rawUncomp,comp=rawComp,offset=rawOffset;
  for(let p=0;p+4<=extra.length;){const kind=u16(extra,p),len=u16(extra,p+2);p+=4;if(p+len>extra.length)break;
    if(kind===1){const view=new DataView(extra.buffer,extra.byteOffset+p,len);let q=0;
      if(uncomp===0xffffffff){uncomp=largeNum(view,q);q+=8}
      if(comp===0xffffffff){comp=largeNum(view,q);q+=8}
      if(offset===0xffffffff){offset=largeNum(view,q);q+=8}
      break
    }p+=len}
  if(uncomp===0xffffffff||comp===0xffffffff||offset===0xffffffff)throw new Error("Incomplete ZIP64 metadata");
  return {uncomp:uncomp,comp:comp,offset:offset}
}
async function* zipEntries(blob){
  const info=await zipInfo(blob);let cursor=info.offset, cache=new Uint8Array(0),cacheBase=-1;
  async function readAt(pos,len){
    if(pos>=cacheBase&&pos+len<=cacheBase+cache.length)return cache.subarray(pos-cacheBase,pos-cacheBase+len);
    cacheBase=pos;cache=await range(blob,pos,Math.min(blob.size,pos+Math.max(262144,len)));
    if(cache.length<len)throw new Error("Truncated central directory");
    return cache.subarray(0,len)
  }
  for(let i=0;i<info.count;i++){
    await pauseCheck();const h=await readAt(cursor,46);
    if(u32(h,0)!==0x02014b50)throw new Error("Invalid ZIP central directory entry "+i);
    const flags=u16(h,8),method=u16(h,10),comp=u32(h,20),uncomp=u32(h,24),nlen=u16(h,28),elen=u16(h,30),clen=u16(h,32),off=u32(h,42);
    const variable=await readAt(cursor+46,nlen+elen);
    const name=decoder.decode(variable.subarray(0,nlen));
    const z=extraZip64(variable.subarray(nlen),uncomp,comp,off);
    cursor+=46+nlen+elen+clen;
    if(name.endsWith("/")||!candidateFile(name))continue;
    yield {name:name,index:i,method:method,flags:flags,compressed:z.comp,uncompressed:z.uncomp,offset:z.offset}
  }
}
async function zipEntryStream(blob,entry){
  const h=await range(blob,entry.offset,entry.offset+30);
  if(h.length<30||u32(h,0)!==0x04034b50)throw new Error("Invalid local ZIP entry");
  const start=entry.offset+30+u16(h,26)+u16(h,28);
  if(start+entry.compressed>blob.size)throw new Error("ZIP entry extends beyond archive");
  if(entry.flags&1)throw new Error("Encrypted ZIP entry is unsupported");
  const part=blob.slice(start,start+entry.compressed);
  if(entry.method===0)return part.stream();
  if(entry.method===8)return part.stream().pipeThrough(new DecompressionStream("deflate-raw"));
  throw new Error("Unsupported ZIP compression method "+entry.method)
}

class NeedMore extends Error{}
function dicomParse(bytes,atEOF){
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),n=bytes.length;
  function ensure(pos,len){if(pos+len>n)throw new NeedMore()}
  function read16(pos,little){ensure(pos,2);return view.getUint16(pos,little)}
  function read32(pos,little){ensure(pos,4);return view.getUint32(pos,little)}
  function tag(pos,little){return read16(pos,little).toString(16).toUpperCase().padStart(4,"0")+read16(pos+2,little).toString(16).toUpperCase().padStart(4,"0")}
  function valueOf(pos,len,vr,little){if(len===0)return "";ensure(pos,len);
    if(vr==="US"&&len===2)return String(read16(pos,little));
    if(vr==="SS"&&len===2)return String(view.getInt16(pos,little));
    if(vr==="UL"&&len===4)return String(read32(pos,little));
    if(len>2048)return "";
    return decoder.decode(bytes.subarray(pos,pos+len)).replace(/\0/g,"").trim()
  }
  const fields={},warnings=[];let p=0,explicit=true,little=true,hasMagic=false,steps=0,gotPixel=false,earlyEnhanced=false;
  try{
    hasMagic=n>=132&&bytes[128]===68&&bytes[129]===73&&bytes[130]===67&&bytes[131]===77;
    p=hasMagic?132:0;ensure(p,8);
    if(!hasMagic){const g=read16(0,true);if(g!==2&&g!==8&&g!==16&&g!==24&&g!==32&&g!==40) return {status:"invalid"}}
    if(tag(p,true).startsWith("0002")){
      while(true){ensure(p,8);const t=tag(p,true);if(!t.startsWith("0002"))break;
        const vr=String.fromCharCode(bytes[p+4],bytes[p+5]);let len=0,head=8;
        if(["OB","OD","OF","OL","OV","OW","SQ","UC","UR","UT","UN","SV","UV"].includes(vr)){ensure(p,12);len=read32(p+8,true);head=12}else len=read16(p+6,true);
        if(t==="00020010")fields.transfer_syntax=valueOf(p+head,len,vr,true);
        p+=head+len;ensure(Math.min(p,n),0);
      }
    }else if(!hasMagic){const vr=String.fromCharCode(bytes[p+4],bytes[p+5]);explicit=/^[A-Z]{2}$/.test(vr)}
    const ts=fields.transfer_syntax||"";
    if(ts==="1.2.840.10008.1.2"){explicit=false;little=true}
    else if(ts==="1.2.840.10008.1.2.2"){explicit=true;little=false}
    else if(ts==="1.2.840.10008.1.2.1.99")return {status:"unsupported",reason:"Deflated DICOM transfer syntax is not supported",fields:fields};
    function parseHeader(pos){ensure(pos,8);const t=tag(pos,little);let vr="UN",length,head=8;
      if(t.startsWith("FFFE")){length=read32(pos+4,little);return {tag:t,vr:"ITEM",length:length,head:8}}
      if(explicit){vr=String.fromCharCode(bytes[pos+4],bytes[pos+5]);
        if(!/^[A-Z]{2}$/.test(vr))throw new Error("Invalid DICOM VR at offset "+pos);
        if(["OB","OD","OF","OL","OV","OW","SQ","UC","UR","UT","UN","SV","UV"].includes(vr)){ensure(pos,12);length=read32(pos+8,little);head=12}
        else length=read16(pos+6,little);
      }else length=read32(pos+4,little);
      return {tag:t,vr:vr,length:length,head:head}
    }
    function scan(start,end,depth,insideFunctional){
      let q=start;
      while(q<end){
        if(++steps>250000)throw new Error("Excessive DICOM element count");
        const h=parseHeader(q),vpos=q+h.head;
        if(h.tag==="7FE00010"||h.tag==="7FE00008"||h.tag==="7FE00009"){gotPixel=true;return {pos:vpos,done:true}}
        if(h.tag==="FFFEE0DD"||h.tag==="FFFEE00D")return {pos:vpos,done:false};
        if(h.tag==="FFFEE000"){const next=h.length===0xffffffff?scan(vpos,end,depth+1,insideFunctional):scan(vpos,vpos+h.length,depth+1,insideFunctional);q=h.length===0xffffffff?next.pos:vpos+h.length;continue}
        if(wanted.has(h.tag)&&h.length!==0xffffffff &&(!insideFunctional||!fields[h.tag])){
          const numeric=h.tag==="00280010"||h.tag==="00280011";
          fields[h.tag]=valueOf(vpos,h.length,numeric?"US":h.vr,little);
        }
        if(h.tag==="52009229"||h.tag==="52009230"){
          earlyEnhanced=true;warnings.push("Enhanced multiframe functional groups detected; first-frame values only");
          const nested=scan(vpos,h.length===0xffffffff?Number.POSITIVE_INFINITY:vpos+h.length,depth+1,true);
          return {pos:nested.pos,done:true}
        }
        if(h.vr==="SQ"||h.length===0xffffffff){
          if(h.length===0xffffffff || (insideFunctional&&depth<12)){
            const nested=scan(vpos,h.length===0xffffffff?end:vpos+h.length,depth+1,insideFunctional);
            q=h.length===0xffffffff?nested.pos:vpos+h.length
          }else q=vpos+h.length;
        }else q=vpos+h.length;
        if(q>n)throw new NeedMore();
      }
      return {pos:q,done:false}
    }
    scan(p,Number.POSITIVE_INFINITY,0,false);
    return {status:"done",fields:fields,warnings:warnings}
  }catch(e){
    if(e instanceof NeedMore)return {status:atEOF?"partial":"need_more",fields:fields,warnings:warnings};
    if(gotPixel||earlyEnhanced)return {status:"done",fields:fields,warnings:warnings};
    return {status:"invalid",reason:e.message,fields:fields,warnings:warnings}
  }
}
async function parseBlob(blob){
  let size=Math.min(blob.size,262144),last=null;
  while(true){await pauseCheck();const bytes=await range(blob,0,size);last=dicomParse(bytes,size===blob.size);
    if(last.status!=="need_more")return last;
    if(size>=HEADER_LIMIT||size>=blob.size)return {status:"partial",fields:last.fields,warnings:(last.warnings||[]).concat("Metadata exceeds read limit")};
    size=Math.min(blob.size,HEADER_LIMIT,size*2);
  }
}
async function parseStream(stream){
  const reader=stream.getReader();let capacity=262144,used=0,bytes=new Uint8Array(capacity),result=null;
  try{while(true){await pauseCheck();const part=await reader.read();
      if(part.done){result=dicomParse(bytes.subarray(0,used),true);break}
      if(used>=HEADER_LIMIT){result={status:"partial",fields:dicomParse(bytes.subarray(0,used),true).fields||{},warnings:["Metadata exceeds read limit"]};break}
      const take=Math.min(part.value.length,HEADER_LIMIT-used);
      while(used+take>capacity){capacity=Math.min(HEADER_LIMIT,capacity*2);const b=new Uint8Array(capacity);b.set(bytes.subarray(0,used));bytes=b}
      bytes.set(part.value.subarray(0,take),used);used+=take;
      result=dicomParse(bytes.subarray(0,used),false);
      if(result.status!=="need_more")break;
    }}finally{try{await reader.cancel()}catch(_){/* stream already finished */}}
  return result||{status:"invalid",reason:"Empty ZIP entry"}
}

function datePart(x){const s=String(x||"");return /^\d{8}$/.test(s)?s.slice(0,4)+"-"+s.slice(4,6)+"-"+s.slice(6,8):""}
function timePart(x){const s=String(x||"");if(!/^\d{2,6}(?:\.\d+)?$/.test(s))return "";return s.slice(0,2)+":"+s.slice(2,4).padEnd(2,"0")+":"+s.slice(4,6).padEnd(2,"0")+(s.includes(".")?s.slice(s.indexOf(".")):"")}
function dateTimePart(x){const s=String(x||"");return s.length>=8?datePart(s.slice(0,8))+(s.length>8?" "+timePart(s.slice(8,14)+s.slice(14).replace(/[+-]\d{4}$/,"")):""):""}
function acquisition(f){return dateTimePart(f["0008002A"])||((datePart(f["00080022"])||datePart(f["00080021"]))+" "+(timePart(f["00080032"])||timePart(f["00080031"]))).trim()}
function actualAcquisition(f){
  const combined=dateTimePart(f["0008002A"]);
  if(combined.includes(" ")&&combined.slice(11))return combined;
  const date=datePart(f["00080022"]),time=timePart(f["00080032"]);
  return date&&time?date+" "+time:""
}
function acquisitionMilliseconds(datetime){
  const m=String(datetime||"").match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?$/);
  if(!m)return null;
  const values=m.slice(1,7).map(Number),ms=Number(((m[7]||"")+"000").slice(0,3));
  const epoch=Date.UTC(values[0],values[1]-1,values[2],values[3],values[4],values[5],ms);
  if(!Number.isFinite(epoch))return null;
  const d=new Date(epoch);
  if(d.getUTCFullYear()!==values[0]||d.getUTCMonth()+1!==values[1]||d.getUTCDate()!==values[2])return null;
  return epoch
}
function localDateTime(epoch){
  if(!Number.isFinite(epoch))return "";
  const iso=new Date(Math.round(epoch)).toISOString().replace("T"," ").replace("Z","");
  return iso.replace(/\.000$/,"")
}
function orientation(raw){if(!raw)return "unknown";const a=raw.split("\\").map(Number);if(a.length!==6||a.some(n=>!Number.isFinite(n)))return "unknown";
  const x=a[1]*a[5]-a[2]*a[4],y=a[2]*a[3]-a[0]*a[5],z=a[0]*a[4]-a[1]*a[3],r=Math.hypot(x,y,z)||1;
  if(Math.abs(z/r)>0.95)return "axial";if(Math.abs(x/r)>0.95)return "sagittal";if(Math.abs(y/r)>0.95)return "coronal";return "oblique"
}
function secondsFromTime(s){const m=String(s||"").match(/^(\d{2}):?(\d{2})(?::?(\d{2}(?:\.\d+)?))?/);return m?Number(m[1])*3600+Number(m[2])*60+Number(m[3]||0):null}
function phaseFromSeconds(seconds){if(seconds<0||seconds>900)return null;
  if(seconds<=35)return {phase:"arterial",conf:"low"};
  if(seconds<=50)return {phase:"arterial",conf:"low"};
  if(seconds>=55&&seconds<=105)return {phase:"portal_venous",conf:seconds>=65?"medium":"low"};
  if(seconds>=180)return {phase:"delayed",conf:"low"};
  return null
}
function estimatePhase(f,path){
  const desc=(f["0008103E"]||"")+" "+(f["00181030"]||"");
  const src=(desc+" "+path).toLowerCase(), result={phase:"unknown",confidence:"unknown",evidence:"No reliable phase indicator",delay:"",conflict:""};
  const patterns=[
    ["non_contrast",/(?:^|[^a-z])(?:non.?contrast|without.?contrast|unenhanced|native|blanco|zonder.?contrast|sans.?iv|pre.?contrast|no.?iv)(?:$|[^a-z])/i],
    ["portal_venous",/(?:^|[^a-z])(?:portal.?venous|portaal.?veneus|portaal|portalphase|venous.?phase|veneuze.?fase|venous|veneus|pv.?phase|v.?phase|pv)(?:$|[^a-z])/i],
    ["arterial",/(?:^|[^a-z])(?:arterial|arterieel|arterialphase|arteriele|art.?phase|artery.?phase)(?:$|[^a-z])/i],
    ["delayed",/(?:^|[^a-z])(?:delayed|delay.?phase|equilibrium|late.?phase|uitgesteld|latevenous)(?:$|[^a-z])/i]
  ];
  const tagMatches=patterns.filter(x=>x[1].test(desc)), folderMatches=patterns.filter(x=>x[1].test(path));
  if(tagMatches.length){result.phase=tagMatches[0][0];result.confidence="high";result.evidence="SeriesDescription/ProtocolName: "+desc.trim()}
  else if(folderMatches.length){result.phase=folderMatches[0][0];result.confidence="medium";result.evidence="Folder/ZIP path: "+path}
  if(new Set(tagMatches.concat(folderMatches).map(x=>x[0])).size>1)result.conflict="Conflicting phase keywords";
  const timing=(desc+" "+path).match(/(?:^|[^a-z0-9])(\d{1,3})\s*(?:s|sec|secs|seconds|sek|seconden)(?=$|[^a-z])/i);
  let delay=timing?Number(timing[1]):null,origin=timing?"Folder/description timing":"";
  const bolus=secondsFromTime(f["00181042"]),acq=secondsFromTime(f["00080032"]||(f["0008002A"]||"").slice(8,14));
  if(bolus!==null&&acq!==null){let d=acq-bolus;if(d< -12*3600)d+=86400;if(d>=0&&d<=900){if(delay!==null&&Math.abs(delay-d)>20)result.conflict+=(result.conflict?"; ":"")+"Folder timing differs from bolus-to-acquisition time";delay=d;origin="DICOM bolus-to-acquisition time"}}
  if(delay!==null){result.delay=String(delay);const guess=phaseFromSeconds(delay);
    if(guess){if(result.phase==="unknown"){result.phase=guess.phase;result.confidence=guess.conf;result.evidence=origin+": "+delay+"s (timing-only estimate)"}
      else if(guess.phase!==result.phase)result.conflict+=(result.conflict?"; ":"")+"Timing suggests "+guess.phase;
      else result.evidence+="; "+origin+": "+delay+"s"
    }else if(result.phase==="unknown")result.evidence=origin+": "+delay+"s; phase uncertain"
  }
  if(result.phase==="unknown"&&f["00180010"])result.evidence+="; contrast agent recorded (phase unknown)";
  return result
}
function makeInfo(p,path,archive){
  const f=p.fields||{},study=f["0020000D"]||"",series=f["0020000E"]||"";
  if(!study||!series)return {invalid:true,reason:"Missing Study/Series Instance UID"};
  const dt=acquisition(f),actualDt=actualAcquisition(f),ph=estimatePhase(f,path),folder=folderIdentity(path);
  return {patient:f["00100020"]||"",folderPatient:folder.patient,followup:folder.followup,
    study:study,studyId:f["00200010"]||"",studyDate:datePart(f["00080020"]),studyTime:timePart(f["00080030"]),
    acq:dt,acqMs:acquisitionMilliseconds(actualDt),bolusStart:timePart(f["00181042"]),imageType:f["00080008"]||"",
    series:series,seriesNum:f["00200011"]||"",desc:f["0008103E"]||"",protocol:f["00181030"]||"",modality:f["00080060"]||"",
    thickness:f["00180050"]||"",spacingTag:f["00180088"]||"",orientation:orientation(f["00200037"]),rows:f["00280010"]||"",cols:f["00280011"]||"",
    pixelSpacing:f["00280030"]||"",contrast:f["00180010"]||"",sop:f["00080018"]||"",frames:Math.max(1,Math.min(1000000,Number(f["00280008"]||1)||1)),
    position:f["00200032"]||"",path:path,archive:archive||"",phase:ph,
    scanType:classifyScan(f,path),parseWarnings:p.warnings||[],status:p.status}
}
function folderIdentity(path){
  const source=String(path||""),outer=source.split("!/")[0];
  // For one-patient ZIPs, identify the patient from the archive filename,
  // never from scan-type directories within the archive.
  const parts=outer.split("/");
  const folder=source.includes("!/")&&/\.zip$/i.test(outer)?
    parts[parts.length-1].replace(/\.zip$/i,"").trim():
    parts.length>1&&!/\.zip$/i.test(parts[0])?parts[0].trim():"";
  const m=folder.match(/^(.*?)[\s_-]+((?:pre|post)(?:[\s_-]?\d+)?)$/i);
  return {patient:(m?m[1]:folder).trim(),followup:m?m[2].toLowerCase().replace(/[\s_-]/g,""):""}
}
function classifyScan(f,path){
  const metadata=[f["0008103E"]||"",f["00181030"]||"",f["00080008"]||""].join(" ");
  const folder=String(path||"").slice(0,String(path||"").lastIndexOf("/"));
  const indicators=[
    ["topogram",/(?:^|[^a-z])topogram(?:$|[^a-z])/i],
    ["scout",/(?:^|[^a-z])scout(?:$|[^a-z])/i],
    ["locator",/(?:^|[^a-z])(?:localizer|localiser|locator)(?:$|[^a-z])/i],
    ["mpr",/(?:^|[^a-z])(?:mpr|mip|reformat|reconstruction\s+coronal)(?:$|[^a-z])/i]
  ];
  for(const [type,pattern] of indicators)if(pattern.test(metadata))return {type:type,evidence:"DICOM description/protocol/image type"};
  for(const [type,pattern] of indicators)if(pattern.test(folder))return {type:type,evidence:"Folder/ZIP path"};
  const modality=f["00080060"]||"",plane=orientation(f["00200037"]);
  if(modality!=="CT")return {type:"non_ct",evidence:"Modality: "+(modality||"missing")};
  if(/(?:^|[^a-z])DERIVED(?:$|[^a-z])/i.test(f["00080008"]||""))return {type:"derived_ct",evidence:"ImageType: DERIVED"};
  return {type:plane==="unknown"?"ct_unknown_orientation":"ct_"+plane,evidence:"CT modality + image orientation (heuristic)"}
}

