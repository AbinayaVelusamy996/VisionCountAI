export default function FrameGallery({frames,selected,onSelect,uploadState,step}){
  const ready=uploadState==='ready'
  return(
    <div className={`card ${step===2?'active-card':''}`}
      style={{padding:16,flex:1,overflow:'hidden',display:'flex',flexDirection:'column',minHeight:0}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12,flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span className={`dot ${step>2?'ok':step===2?'on':''}`}>{step>2?'✓':'2'}</span>
          <span style={{fontSize:11,fontWeight:600,letterSpacing:'.06em'}}>FRAME GALLERY</span>
        </div>
        {ready&&<span style={{fontSize:10,color:'var(--tx2)'}}>{frames.length} frames</span>}
      </div>
      {!ready
        ?<div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center'}}>
            <div style={{textAlign:'center',opacity:.25}}>
              <div style={{fontSize:28,marginBottom:8}}>⬚</div>
              <div style={{fontSize:11}}>Upload a video first</div>
            </div>
          </div>
        :<>
          <div style={{flex:1,overflowY:'auto',display:'grid',gridTemplateColumns:'1fr 1fr',gap:7,paddingRight:2}}>
            {frames.map(f=>(
              <div key={f.id} className={`thumb ${selected?.id===f.id?'sel':''}`} onClick={()=>onSelect(f)}>
                <div style={{position:'relative',aspectRatio:'16/9',background:'var(--bg4)'}}>
                  <img src={f.url} alt={f.id} loading="lazy"
                    style={{width:'100%',height:'100%',objectFit:'cover',display:'block'}}/>
                  <div style={{position:'absolute',bottom:3,right:4,fontSize:9,
                    color:'rgba(255,255,255,.9)',background:'rgba(0,0,0,.6)',
                    padding:'1px 4px',borderRadius:2}}>{f.timestamp}</div>
                  <div style={{position:'absolute',top:3,left:4,fontSize:9,
                    color:'rgba(255,255,255,.9)',background:'rgba(0,0,0,.6)',
                    padding:'1px 4px',borderRadius:2}}>{f.id}</div>
                  {selected?.id===f.id&&<div style={{position:'absolute',inset:0,
                    background:'rgba(0,212,170,.1)',border:'2px solid var(--ac)',borderRadius:4}}/>}
                </div>
              </div>
            ))}
          </div>
          <div style={{flexShrink:0,marginTop:8,fontSize:10,color:'var(--tx2)',textAlign:'center'}}>
            ↑ Select a frame then draw the counting line
          </div>
        </>
      }
    </div>
  )
}
