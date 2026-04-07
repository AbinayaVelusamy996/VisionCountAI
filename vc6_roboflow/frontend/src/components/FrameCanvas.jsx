import{useRef,useEffect,useState,useCallback}from'react'
const W=800,H=450

export default function FrameCanvas({frame,onLineSaved,procState,onProcess,step,progress,modelReady,liveImg,liveDets,isWarmup}){
  const cvRef=useRef(); const imgRef=useRef(null); const liveRef=useRef(null)
  const st=useRef({drawing:false,start:null,hover:null})
  const[saved,setSaved]=useState(null); const[loaded,setLoaded]=useState(false)
  const[,tick]=useState(0)
  const isP=procState==='processing'; const isD=procState==='done'

  const xy=useCallback(e=>{
    const r=cvRef.current.getBoundingClientRect()
    return{x:Math.round((e.clientX-r.left)*(W/r.width)),y:Math.round((e.clientY-r.top)*(H/r.height))}
  },[])

  const paint=useCallback(()=>{
    const cv=cvRef.current; if(!cv) return
    const ctx=cv.getContext('2d'); ctx.clearRect(0,0,W,H)
    // During processing: show live annotated video feed
    if(isP && liveRef.current){ ctx.drawImage(liveRef.current,0,0,W,H); return }
    if(!frame){
      ctx.fillStyle='#07090d'; ctx.fillRect(0,0,W,H)
      ctx.strokeStyle='rgba(255,255,255,.03)'; ctx.lineWidth=1
      for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke()}
      for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke()}
      ctx.fillStyle='rgba(255,255,255,.15)'; ctx.font='13px IBM Plex Mono'; ctx.textAlign='center'
      ctx.fillText('← Select a frame from the gallery',W/2,H/2); return
    }
    if(imgRef.current&&loaded) ctx.drawImage(imgRef.current,0,0,W,H)
    else{ ctx.fillStyle='#0d1117'; ctx.fillRect(0,0,W,H) }
    const{drawing,start,hover}=st.current
    if(drawing&&start&&hover&&!saved) drawLine(ctx,start.x,start.y,hover.x,hover.y,false)
    if(saved) drawLine(ctx,saved.x1,saved.y1,saved.x2,saved.y2,true)
  },[frame,saved,loaded,isP])

  function drawLine(ctx,x1,y1,x2,y2,final){
    ctx.shadowColor='#00d4aa'; ctx.shadowBlur=final?16:6
    ctx.strokeStyle=final?'#00d4aa':'rgba(0,212,170,.55)'
    ctx.lineWidth=final?3:2; ctx.setLineDash(final?[]:[10,6])
    ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke()
    ctx.setLineDash([]); ctx.shadowBlur=0
    if(final){
      const dx=x2-x1,dy=y2-y1,L=Math.hypot(dx,dy)||1,mx=(x1+x2)/2,my=(y1+y2)/2,px=-dy/L,py=dx/L
      arrow(ctx,mx,my,mx+px*50,my+py*50,'#00d4aa','IN')
      arrow(ctx,mx,my,mx-px*50,my-py*50,'#f87171','OUT')
      ;[[x1,y1],[x2,y2]].forEach(([ex,ey])=>{
        ctx.fillStyle='#00d4aa'; ctx.shadowColor='#00d4aa'; ctx.shadowBlur=8
        ctx.beginPath(); ctx.arc(ex,ey,5,0,Math.PI*2); ctx.fill(); ctx.shadowBlur=0
      })
      ctx.fillStyle='rgba(0,0,0,.75)'; ctx.fillRect(x1,y1-26,130,18)
      ctx.fillStyle='#00d4aa'; ctx.font='10px IBM Plex Mono'; ctx.textAlign='left'
      ctx.fillText(`(${x1},${y1}) -> (${x2},${y2})`,x1+4,y1-12)
    }else{
      ctx.fillStyle='#00d4aa'; ctx.beginPath(); ctx.arc(x1,y1,5,0,Math.PI*2); ctx.fill()
    }
  }

  function arrow(ctx,fx,fy,tx,ty,col,lbl){
    const dx=tx-fx,dy=ty-fy,L=Math.hypot(dx,dy)||1,ux=dx/L,uy=dy/L
    ctx.strokeStyle=col; ctx.fillStyle=col; ctx.lineWidth=1.5
    ctx.beginPath(); ctx.moveTo(fx,fy); ctx.lineTo(tx,ty); ctx.stroke()
    const ax=tx-ux*8-uy*4,ay=ty-uy*8+ux*4,bx=tx-ux*8+uy*4,by=ty-uy*8-ux*4
    ctx.beginPath(); ctx.moveTo(tx,ty); ctx.lineTo(ax,ay); ctx.lineTo(bx,by); ctx.closePath(); ctx.fill()
    ctx.font='bold 11px IBM Plex Mono'; ctx.textAlign='center'
    ctx.fillText(lbl,tx+ux*14,ty+uy*14+4)
  }

  useEffect(()=>{
    setSaved(null); st.current={drawing:false,start:null,hover:null}; setLoaded(false)
    if(!frame){paint();return}
    const img=new Image(); img.crossOrigin='anonymous'
    img.onload=()=>{imgRef.current=img;setLoaded(true)}
    img.onerror=()=>{imgRef.current=null;paint()}
    img.src=frame.url
  },[frame])
  useEffect(()=>paint(),[paint,loaded,saved])

  // Decode incoming base64 live frame and paint immediately
  useEffect(()=>{
    if(!liveImg) return
    const img=new Image()
    img.onload=()=>{liveRef.current=img; paint()}
    img.src=`data:image/jpeg;base64,${liveImg}`
  },[liveImg])

  const onDown=e=>{if(!frame||saved||isP||isD)return;const p=xy(e);st.current={drawing:true,start:p,hover:p}}
  const onMove=e=>{if(!st.current.drawing)return;st.current.hover=xy(e);paint()}
  const onUp=e=>{
    const{drawing,start}=st.current; if(!drawing||!start)return
    const end=xy(e); st.current={drawing:false,start:null,hover:null}
    if(Math.hypot(end.x-start.x,end.y-start.y)<12){paint();return}
    const l={x1:start.x,y1:start.y,x2:end.x,y2:end.y}
    setSaved(l); onLineSaved(l)
  }
  const reset=()=>{
    st.current={drawing:false,start:null,hover:null}
    setSaved(null); onLineSaved(null); liveRef.current=null; tick(n=>n+1); setTimeout(paint,10)
  }
  const canStart=saved&&modelReady&&!isP&&!isD

  return(
    <div style={{display:'flex',flexDirection:'column',gap:12,flex:1,overflow:'hidden'}}>
      <div className={`card ${step===3?'active-card':''}`}
        style={{flex:1,padding:16,display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12,flexShrink:0,flexWrap:'wrap'}}>
          <span className={`dot ${step>3?'ok':step===3?'on':''}`}>{step>3?'✓':'3'}</span>
          <span style={{fontSize:11,fontWeight:600,letterSpacing:'.06em'}}>FRAME CANVAS</span>
          {frame&&!isP&&<span style={{fontSize:10,color:'var(--tx2)',marginLeft:4}}>{frame.id} · {frame.timestamp}</span>}
          {isP&&<span style={{display:'flex',alignItems:'center',gap:6,fontSize:10,
            color:isWarmup?'var(--yw)':'var(--ac)',marginLeft:8}}>
            {!isWarmup&&<span className="pdot"/>}
            {isWarmup?'⏳ Initializing…':`LIVE · ${liveDets??0} objects`}
          </span>}
          <div style={{marginLeft:'auto',display:'flex',gap:8,alignItems:'center'}}>
            {!saved&&frame&&!isP&&!isD&&(
              <span style={{fontSize:10,color:'var(--a2)',display:'flex',alignItems:'center',gap:5}}>
                <span className="pdot" style={{width:6,height:6}}/> Click-drag to draw counting line
              </span>
            )}
            {saved&&!isP&&!isD&&<button className="btn-sm" onClick={reset}>↺ Redraw Line</button>}
          </div>
        </div>

        <div style={{flex:1,position:'relative',borderRadius:8,overflow:'hidden',background:'#000',minHeight:0}}>
          <canvas ref={cvRef} width={W} height={H}
            onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
            style={{width:'100%',height:'100%',display:'block',userSelect:'none',
              cursor:!frame||isP||isD?'default':saved?'default':'crosshair'}}/>

          {/* Thin progress bar at bottom — doesn't block the video */}
          {isP&&(
            <div style={{position:'absolute',bottom:0,left:0,right:0,height:4,background:'rgba(0,0,0,.4)'}}>
              <div style={{height:'100%',background:'linear-gradient(90deg,var(--ac),var(--a2))',
                width:`${progress||0}%`,transition:'width .5s ease'}}/>
            </div>
          )}
          {/* Small HUD when no live frames yet */}
          {isP&&!liveImg&&(
            <div style={{position:'absolute',top:'50%',left:'50%',transform:'translate(-50%,-50%)',
              display:'flex',flexDirection:'column',alignItems:'center',gap:12}}>
              <div style={{width:36,height:36,border:'3px solid var(--ac)',borderTopColor:'transparent',
                borderRadius:'50%'}} className="spin"/>
              <div style={{fontSize:12,color:'var(--ac)',fontWeight:600}}>Starting detection…</div>
            </div>
          )}
          {isD&&(
            <div style={{position:'absolute',bottom:12,left:'50%',transform:'translateX(-50%)',
              background:'rgba(0,212,170,.15)',border:'1px solid var(--ac)',borderRadius:8,
              padding:'6px 18px',fontSize:11,color:'var(--ac)',whiteSpace:'nowrap',fontWeight:600}}>
              ✓ Detection complete — view results →
            </div>
          )}
        </div>
      </div>

      {saved&&(
        <div className="card fu" style={{padding:'12px 16px',display:'flex',alignItems:'center',gap:16,flexShrink:0,flexWrap:'wrap'}}>
          <div>
            <div style={{fontSize:9,color:'var(--tx2)',letterSpacing:'.08em',marginBottom:3}}>COUNTING LINE</div>
            <code style={{fontSize:11,color:'var(--ac)'}}>({saved.x1},{saved.y1}) → ({saved.x2},{saved.y2})</code>
          </div>
          {frame&&(
            <div>
              <div style={{fontSize:9,color:'var(--tx2)',letterSpacing:'.08em',marginBottom:3}}>START FROM</div>
              <code style={{fontSize:11,color:'var(--a2)'}}>{frame.id} · {frame.timestamp}</code>
            </div>
          )}
          {!modelReady&&!isP&&!isD&&(
            <div style={{display:'flex',alignItems:'center',gap:7,fontSize:10,color:'var(--yw)'}}>
              <div style={{width:11,height:11,border:'1.5px solid var(--yw)',borderTopColor:'transparent',borderRadius:'50%'}} className="spin"/>
              Model loading…
            </div>
          )}
          <div style={{marginLeft:'auto'}}>
            <button className="btn" disabled={!canStart} onClick={onProcess}>
              {isP?<><div style={{width:12,height:12,border:'2px solid #000',borderTopColor:'transparent',borderRadius:'50%'}} className="spin"/>Detecting…</>
                :isD?'✓ Complete'
                :!modelReady?'⌛ Model Loading…'
                :'▶  Start Detection'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
