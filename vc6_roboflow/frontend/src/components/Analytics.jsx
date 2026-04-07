import{useEffect,useRef,useState}from'react'

const CATS=['Male','Female','Bicycle','Animal','Vehicle']
const M={
  Male:    {icon:'♂', color:'#3b82f6', bg:'rgba(59,130,246,.1)',  bd:'rgba(59,130,246,.25)'},
  Female:  {icon:'♀', color:'#ec4899', bg:'rgba(236,72,153,.1)',  bd:'rgba(236,72,153,.25)'},
  Bicycle: {icon:'◉', color:'#fbbf24', bg:'rgba(251,191,36,.1)',  bd:'rgba(251,191,36,.25)'},
  Animal:  {icon:'◆', color:'#a78bfa', bg:'rgba(167,139,250,.1)', bd:'rgba(167,139,250,.25)'},
  Vehicle: {icon:'■', color:'#4ade80', bg:'rgba(74,222,128,.1)',  bd:'rgba(74,222,128,.25)'},
}

function LiveNum({v,col}){
  const[bump,setBump]=useState(false);const prev=useRef(v)
  useEffect(()=>{
    if(v!==prev.current){prev.current=v;setBump(true)
      const t=setTimeout(()=>setBump(false),350);return()=>clearTimeout(t)}
  },[v])
  return<span style={{fontSize:26,fontFamily:'var(--fd)',fontWeight:800,color:col,
    display:'inline-block',lineHeight:1,
    transform:bump?'scale(1.28)':'scale(1)',
    transition:'transform .18s cubic-bezier(.34,1.56,.64,1)'}}>{v}</span>
}

function ClassCard({name,inC,outC,live}){
  const m=M[name];const tot=inC+outC;const pct=tot>0?Math.round(inC/tot*100):50
  return(
    <div style={{background:m.bg,border:`1px solid ${m.bd}`,borderRadius:10,padding:14}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10}}>
        <div style={{display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontSize:16,color:m.color}}>{m.icon}</span>
          <span style={{fontSize:12,fontWeight:600}}>{name}</span>
          {live&&tot>0&&<span style={{width:5,height:5,borderRadius:'50%',
            background:m.color,display:'inline-block',animation:'pulse-a 1.5s infinite'}}/>}
        </div>
        <span style={{fontSize:10,color:'var(--tx2)'}}>Σ {tot}</span>
      </div>
      <div style={{display:'flex',gap:8,marginBottom:8}}>
        <div style={{flex:1,textAlign:'center',padding:'7px 4px',
          background:'rgba(0,212,170,.1)',border:'1px solid rgba(0,212,170,.25)',borderRadius:8}}>
          <div style={{fontSize:9,color:'var(--ac)',letterSpacing:'.05em',marginBottom:3}}>↓ IN</div>
          <LiveNum v={inC} col="var(--ac)"/>
        </div>
        <div style={{flex:1,textAlign:'center',padding:'7px 4px',
          background:'rgba(248,113,113,.1)',border:'1px solid rgba(248,113,113,.25)',borderRadius:8}}>
          <div style={{fontSize:9,color:'var(--rd)',letterSpacing:'.05em',marginBottom:3}}>↑ OUT</div>
          <LiveNum v={outC} col="var(--rd)"/>
        </div>
      </div>
      <div style={{height:3,background:'var(--bd)',borderRadius:2,overflow:'hidden'}}>
        <div style={{height:'100%',width:`${pct}%`,
          background:`linear-gradient(90deg,var(--ac),${m.color})`,
          borderRadius:2,transition:'width .5s ease'}}/>
      </div>
      <div style={{display:'flex',justifyContent:'space-between',marginTop:3}}>
        <span style={{fontSize:9,color:'var(--tx2)'}}>{pct}% in</span>
        <span style={{fontSize:9,color:'var(--tx2)'}}>{100-pct}% out</span>
      </div>
    </div>
  )
}

function EventBadge({item}){
  const meta=M[item.cat]||M['Bicycle']
  return(
    <div className={`fu ${item.direction==='IN'?'flash-in':'flash-out'}`}
      style={{display:'flex',alignItems:'center',gap:8,padding:'6px 10px',borderRadius:7,marginBottom:4,
        background:item.direction==='IN'?'rgba(0,212,170,.07)':'rgba(248,113,113,.07)',
        border:`1px solid ${item.direction==='IN'?'rgba(0,212,170,.2)':'rgba(248,113,113,.2)'}`}}>
      <span style={{fontSize:14,color:meta.color}}>{meta.icon}</span>
      <div style={{flex:1,minWidth:0}}>
        <span style={{fontSize:11,fontWeight:600,color:meta.color}}>{item.cat}</span>
        <span style={{fontSize:10,color:'var(--tx2)',marginLeft:5}}>#{item.tid}</span>
      </div>
      <span style={{fontSize:10,fontWeight:700,letterSpacing:'.05em',
        color:item.direction==='IN'?'var(--ac)':'var(--rd)'}}>
        {item.direction==='IN'?'↓ IN':'↑ OUT'}
      </span>
      <span style={{fontSize:9,color:'var(--tx2)',minWidth:34,textAlign:'right'}}>{item.timestamp}s</span>
    </div>
  )
}

export default function Analytics({counters,feed,procState,step,progress,outputUrl,analytics,modelReady,apiOnline}){
  const live=procState==='processing'; const done=procState==='done'
  const feedRef=useRef()
  useEffect(()=>{if(feedRef.current)feedRef.current.scrollTop=0},[feed.length])
  const totalIn=CATS.reduce((s,c)=>s+(counters[c]?.IN||0),0)
  const totalOut=CATS.reduce((s,c)=>s+(counters[c]?.OUT||0),0)

  return(
    <div style={{display:'flex',flexDirection:'column',gap:12}}>

      {!apiOnline&&(
        <div style={{background:'rgba(248,113,113,.1)',border:'1px solid rgba(248,113,113,.3)',
          borderRadius:8,padding:'10px 14px',fontSize:10}}>
          <span style={{color:'var(--rd)',fontWeight:600}}>⚠ Backend Offline</span>
          <span style={{color:'var(--tx2)',marginLeft:8}}>Run start_backend.sh first</span>
        </div>
      )}
      {apiOnline&&!modelReady&&(
        <div style={{background:'rgba(251,191,36,.08)',border:'1px solid rgba(251,191,36,.3)',
          borderRadius:8,padding:'10px 14px',display:'flex',alignItems:'center',gap:10}}>
          <div style={{width:12,height:12,border:'2px solid var(--yw)',
            borderTopColor:'transparent',borderRadius:'50%',flexShrink:0}} className="spin"/>
          <div>
            <div style={{fontSize:11,fontWeight:600,color:'var(--yw)'}}>Loading YOLO + Gender model…</div>
            <div style={{fontSize:10,color:'var(--tx2)'}}>First-time load ~40s. Unlocks automatically.</div>
          </div>
        </div>
      )}

      {/* Totals */}
      <div className={`card ${step>=4?'active-card':''}`} style={{padding:16}}>
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:12}}>
          <span className={`dot ${done?'ok':live?'on':''}`}>{done?'✓':'4'}</span>
          <span style={{fontSize:11,fontWeight:600,letterSpacing:'.06em'}}>LIVE ANALYTICS</span>
          {live&&<div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:6}}>
            <span className="pdot"/>
            <span style={{fontSize:10,color:'var(--ac)',fontWeight:600,letterSpacing:'.06em'}}>STREAMING</span>
          </div>}
          {done&&<span style={{marginLeft:'auto',fontSize:10,color:'var(--ac)',fontWeight:600}}>✓ Done</span>}
        </div>
        {live&&(
          <div style={{marginBottom:12}}>
            <div className="prog">
              <div className="prog-fill" style={{width:`${progress}%`,transition:'width .5s ease'}}/>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',marginTop:5}}>
              <span style={{fontSize:9,color:'var(--tx2)'}}>Processing frames</span>
              <span style={{fontSize:9,color:'var(--ac)',fontWeight:600}}>{progress}%</span>
            </div>
          </div>
        )}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
          <div style={{background:'rgba(0,212,170,.07)',border:'1px solid rgba(0,212,170,.2)',
            borderRadius:10,padding:14,textAlign:'center'}}>
            <div style={{fontSize:9,color:'var(--tx2)',letterSpacing:'.08em',marginBottom:5}}>TOTAL IN</div>
            <LiveNum v={totalIn} col="var(--ac)"/>
            <div style={{fontSize:14,marginTop:3,color:'var(--ac)'}}>↓</div>
          </div>
          <div style={{background:'rgba(248,113,113,.07)',border:'1px solid rgba(248,113,113,.2)',
            borderRadius:10,padding:14,textAlign:'center'}}>
            <div style={{fontSize:9,color:'var(--tx2)',letterSpacing:'.08em',marginBottom:5}}>TOTAL OUT</div>
            <LiveNum v={totalOut} col="var(--rd)"/>
            <div style={{fontSize:14,marginTop:3,color:'var(--rd)'}}>↑</div>
          </div>
        </div>
      </div>

      {/* All 5 classes as equal siblings */}
      <div className="card" style={{padding:16}}>
        <div style={{fontSize:10,color:'var(--tx2)',letterSpacing:'.08em',marginBottom:12}}>
          CLASS BREAKDOWN
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          {CATS.map(c=>(
            <ClassCard key={c} name={c}
              inC={counters[c]?.IN||0} outC={counters[c]?.OUT||0} live={live}/>
          ))}
        </div>
      </div>

      {/* Crossing feed */}
      {(live||done||feed.length>0)&&(
        <div className="card" style={{padding:16}}>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
            <span style={{fontSize:10,color:'var(--tx2)',letterSpacing:'.08em'}}>CROSSING FEED</span>
            {live&&<span className="pdot" style={{width:5,height:5,marginLeft:'auto'}}/>}
            <span style={{fontSize:9,color:'var(--tx2)',marginLeft:live?0:'auto'}}>{feed.length} events</span>
          </div>
          <div ref={feedRef} style={{maxHeight:220,overflowY:'auto'}}>
            {feed.length===0?(
              <div style={{textAlign:'center',padding:'16px 0',color:'var(--tx2)',fontSize:10}}>
                Crossings appear here in real-time
              </div>
            ):feed.map(item=><EventBadge key={item.key} item={item}/>)}
          </div>
        </div>
      )}

      {/* Download */}
      {done&&outputUrl&&(
        <div className="card" style={{padding:16}}>
          <div style={{fontSize:10,color:'var(--tx2)',letterSpacing:'.08em',marginBottom:12}}>RESULTS</div>
          <a href={outputUrl} download style={{display:'block',width:'100%',textDecoration:'none'}}>
            <button className="btn" style={{width:'100%'}}>↓ Download Annotated Video</button>
          </a>
          {analytics?.meta&&(
            <div style={{marginTop:12,display:'flex',flexDirection:'column',gap:4}}>
              {Object.entries(analytics.meta).map(([k,v])=>(
                <div key={k} style={{display:'flex',justifyContent:'space-between',
                  padding:'4px 0',borderBottom:'1px solid var(--bd)'}}>
                  <span style={{fontSize:9,color:'var(--tx2)',textTransform:'uppercase',letterSpacing:'.06em'}}>{k.replace(/_/g,' ')}</span>
                  <code style={{fontSize:9,color:'var(--tx)'}}>{v}</code>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
