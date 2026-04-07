import{useRef,useState}from'react'
export default function UploadPanel({state,pct,onUpload,step,info}){
  const[drag,setDrag]=useState(false);const ref=useRef()
  const go=files=>{
    const f=files[0];if(!f)return
    const ext=f.name.split('.').pop().toLowerCase()
    if(!['mp4','mov','avi','mkv','webm'].includes(ext)){alert(`Unsupported .${ext}`);return}
    onUpload(f)
  }
  const p=Math.min(Math.round(pct),100)
  const active=step===1
  return(
    <div className={`card ${active?'active-card':''}`} style={{padding:16,flexShrink:0}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span className={`dot ${step>1?'ok':active?'on':''}`}>{step>1?'✓':'1'}</span>
          <span style={{fontSize:11,fontWeight:600,letterSpacing:'.06em'}}>UPLOAD VIDEO</span>
        </div>
        {state==='ready'&&<span style={{fontSize:10,color:'var(--ac)',fontWeight:600}}>● READY</span>}
      </div>

      <div onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)}
        onDrop={e=>{e.preventDefault();setDrag(false);go(e.dataTransfer.files)}}
        onClick={()=>state==='idle'&&ref.current?.click()}
        style={{border:`2px dashed ${drag||state==='ready'?'var(--ac)':state==='error'?'var(--rd)':'var(--bd)'}`,
          borderRadius:10,padding:'16px 12px',textAlign:'center',
          cursor:state==='idle'?'pointer':'default',
          background:drag?'rgba(0,212,170,.05)':'var(--bg3)',
          transition:'all .2s',minHeight:90,display:'flex',alignItems:'center',justifyContent:'center'}}>
        {state==='idle'&&<div>
          <div style={{fontSize:22,marginBottom:6}}>⬆</div>
          <div style={{fontSize:12,fontWeight:600,marginBottom:4}}>Drop video / click to browse</div>
          <div style={{fontSize:10,color:'var(--tx2)'}}>MP4 · MOV · AVI · MKV · WEBM</div>
        </div>}
        {state==='uploading'&&<div style={{width:'100%'}}>
          <div style={{fontSize:9,color:'var(--tx2)',marginBottom:6}}>UPLOADING</div>
          <div style={{fontSize:22,fontFamily:'var(--fd)',fontWeight:700,color:'var(--ac)',marginBottom:8}}>{p}%</div>
          <div className="prog"><div className="prog-fill" style={{width:`${p}%`}}/></div>
        </div>}
        {state==='extracting'&&<div style={{width:'100%',textAlign:'center'}}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'center',gap:8,marginBottom:8}}>
            <div style={{width:14,height:14,border:'2px solid var(--ac)',borderTopColor:'transparent',borderRadius:'50%'}} className="spin"/>
            <span style={{fontSize:10}}>EXTRACTING FRAMES…</span>
          </div>
          <div className="prog"><div className="prog-fill" style={{width:'100%'}}/></div>
        </div>}
        {state==='ready'&&<div>
          <div style={{fontSize:20,color:'var(--ac)',marginBottom:4}}>✓</div>
          <div style={{fontSize:12,fontWeight:600,color:'var(--ac)'}}>Ready</div>
          {info&&<div style={{fontSize:10,color:'var(--tx2)',marginTop:3}}>
            {info.total_frames} frames · {info.fps} fps · {info.resolution}
          </div>}
        </div>}
        {state==='error'&&<div>
          <div style={{fontSize:20,color:'var(--rd)',marginBottom:4}}>✕</div>
          <div style={{fontSize:11,color:'var(--rd)'}}>Failed — click to retry</div>
        </div>}
      </div>
      <input ref={ref} type="file" accept=".mp4,.mov,.avi,.mkv,.webm"
        style={{display:'none'}} onChange={e=>go(e.target.files)}/>
    </div>
  )
}
