export function uploadVideo(file,onPct){
  return new Promise((res,rej)=>{
    const xhr=new XMLHttpRequest(),form=new FormData()
    form.append('file',file)
    xhr.upload.addEventListener('progress',e=>{if(e.lengthComputable)onPct(e.loaded/e.total*100)})
    xhr.addEventListener('load',()=>{
      if(xhr.status===200){try{res(JSON.parse(xhr.responseText))}catch{rej(new Error('Bad JSON'))}}
      else{try{rej(new Error(JSON.parse(xhr.responseText).detail||`HTTP ${xhr.status}`))}catch{rej(new Error(`HTTP ${xhr.status}`))}}
    })
    xhr.addEventListener('error',()=>rej(new Error('Network error')))
    xhr.open('POST','/api/upload'); xhr.send(form)
  })
}

export async function startProcessing({job_id, x1, y1, x2, y2, start_frame=0}){
  const r=await fetch('/api/process',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({job_id, x1, y1, x2, y2, start_frame})
  })
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${r.status}`)}
  return r.json()
}

export function openStream(job_id,{onFrame,onCrossing,onDone,onError}){
  const es=new EventSource(`/api/stream/${job_id}`)
  es.addEventListener('frame',    e=>{try{onFrame?.(JSON.parse(e.data))}catch(err){console.error('frame:',err)}})
  es.addEventListener('crossing', e=>{try{onCrossing?.(JSON.parse(e.data))}catch(err){console.error('crossing:',err)}})
  es.addEventListener('done',     e=>{try{onDone?.(JSON.parse(e.data));es.close()}catch(err){console.error('done:',err)}})
  es.addEventListener('error',    e=>{if(e.data){try{onError?.(JSON.parse(e.data).message)}catch{onError?.('Stream error')}}})
  es.addEventListener('closed',   ()=>es.close())
  return ()=>es.close()
}

export async function checkHealth(){
  try{
    const r=await fetch('/api/health',{signal:AbortSignal.timeout(3000)})
    if(!r.ok) return{online:false,modelReady:false}
    const d=await r.json()
    return{online:true,modelReady:!!d.model_ready}
  }catch{return{online:false,modelReady:false}}
}
