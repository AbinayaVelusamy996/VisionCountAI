import{useState,useEffect,useRef}from'react'
import UploadPanel from'./components/UploadPanel.jsx'
import FrameGallery from'./components/FrameGallery.jsx'
import FrameCanvas from'./components/FrameCanvas.jsx'
import Analytics from'./components/Analytics.jsx'
import{uploadVideo,startProcessing,checkHealth,openStream}from'./utils/api.js'
import'./styles/globals.css'

// Male & Female are now first-class categories, just like Bicycle
const INIT_C={Male:{IN:0,OUT:0},Female:{IN:0,OUT:0},Bicycle:{IN:0,OUT:0},Animal:{IN:0,OUT:0},Vehicle:{IN:0,OUT:0}}
const STEPS=['Upload','Frames','Draw Line','Live Feed','Results']

export default function App(){
  const[dark,setDark]=useState(true)
  const[step,setStep]=useState(1)
  const[apiOnline,setApi]=useState(false)
  const[modelReady,setModel]=useState(false)
  const[uploadState,setUS]=useState('idle')
  const[uploadPct,setUP]=useState(0)
  const[info,setInfo]=useState(null)
  const[frames,setFrames]=useState([])
  const[selFrame,setSel]=useState(null)
  const[line,setLine]=useState(null)
  const[jobId,setJob]=useState(null)
  const[procState,setPS]=useState('idle')
  const[progress,setProg]=useState(0)
  const[counters,setC]=useState(INIT_C)
  const[feed,setFeed]=useState([])
  const[analytics,setAn]=useState(null)
  const[outputUrl,setOut]=useState(null)
  const[liveImg,setLiveImg]=useState(null)
  const[liveDets,setLiveDets]=useState(null)
  const[isWarmup,setWarmup]=useState(false)
  const streamRef=useRef(null)
  const pollRef=useRef(null)

  useEffect(()=>{
    const poll=async()=>{
      const h=await checkHealth()
      setApi(h.online)
      if(h.modelReady){setModel(true);clearInterval(pollRef.current)}
    }
    poll(); pollRef.current=setInterval(poll,2500)
    return()=>clearInterval(pollRef.current)
  },[])

  useEffect(()=>{document.documentElement.className=dark?'':'light'},[dark])

  const handleUpload=async file=>{
    setUS('uploading');setUP(0);setStep(1)
    try{
      const d=await uploadVideo(file,p=>setUP(p))
      setJob(d.job_id);setInfo(d);setUS('extracting')
      await new Promise(r=>setTimeout(r,300))
      setFrames(d.frames);setUS('ready');setStep(2)
    }catch(e){console.error(e);setUS('error')}
  }

  const handleProcess=async()=>{
    if(!line||!jobId||!modelReady) return
    const start_frame=selFrame?.frame_idx??0
    setC(INIT_C);setFeed([]);setAn(null);setOut(null)
    setProg(0);setLiveImg(null);setLiveDets(null);setWarmup(true)
    setPS('processing');setStep(4)
    streamRef.current?.();streamRef.current=null
    try{
      await startProcessing({job_id:jobId,...line,start_frame})
      streamRef.current=openStream(jobId,{
        onFrame:d=>{
          setProg(d.progress||0)
          if(d.counters)setC(p=>({...p,...d.counters}))
          if(d.img)setLiveImg(d.img)
          if(d.dets!=null)setLiveDets(d.dets)
          setWarmup(!!d.warmup)
        },
        onCrossing:d=>{
          if(d.counters)setC(p=>({...p,...d.counters}))
          setFeed(p=>[{
            cat:d.cat,direction:d.direction,tid:d.tid,
            timestamp:d.timestamp,key:`${d.tid}-${d.frame}`
          },...p].slice(0,80))
        },
        onDone:d=>{
          streamRef.current=null;setPS('done');setStep(5);setProg(100)
          if(d.analytics){
            setAn(d.analytics)
            if(d.analytics.classes){
              const f={};d.analytics.classes.forEach(c=>{f[c.name]={IN:c.in,OUT:c.out}})
              setC(p=>({...p,...f}))
            }
          }
          if(d.output_url)setOut(d.output_url)
        },
        onError:msg=>{console.error(msg);setPS('error')}
      })
    }catch(e){console.error(e);setPS('error');setStep(3);alert(`Failed: ${e.message}`)}
  }

  return(
    <div style={{display:'flex',flexDirection:'column',height:'100vh',overflow:'hidden'}}>
      <header style={{height:56,flexShrink:0,background:'var(--bg2)',borderBottom:'1px solid var(--bd)',
        display:'flex',alignItems:'center',padding:'0 20px',gap:20,zIndex:100}}>
        <div style={{display:'flex',alignItems:'center',gap:10,minWidth:200}}>
          <div style={{width:34,height:34,borderRadius:9,
            background:'linear-gradient(135deg,var(--ac),var(--a2))',
            display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:16,fontWeight:800,color:'#000',fontFamily:'var(--fd)'}}>V</div>
          <div>
            <div style={{fontFamily:'var(--fd)',fontWeight:700,fontSize:15,lineHeight:1.1}}>
              VisionCount
              <span style={{fontSize:9,color:'var(--ac)',fontFamily:'var(--ff)',marginLeft:6}}>v6</span>
            </div>
            <div style={{fontSize:9,color:'var(--tx2)',letterSpacing:'.1em',textTransform:'uppercase'}}>YOLOv8m · DeepFace Gender</div>
          </div>
        </div>

        <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',gap:3}}>
          {STEPS.map((s,i)=>(
            <div key={i} style={{display:'flex',alignItems:'center',gap:3}}>
              <div style={{display:'flex',alignItems:'center',gap:5}}>
                <span className={`dot ${step>i+1?'ok':step===i+1?'on':''}`}>{step>i+1?'✓':i+1}</span>
                {step>=i&&<span style={{fontSize:10,fontWeight:step===i+1?600:400,
                  color:step>=i+1?'var(--tx)':'var(--tx2)'}}>{s}</span>}
              </div>
              {i<STEPS.length-1&&<div style={{width:16,height:1,margin:'0 2px',
                background:step>i+1?'var(--ac)':'var(--bd)',transition:'background .3s'}}/>}
            </div>
          ))}
        </div>

        <div style={{display:'flex',alignItems:'center',gap:14,minWidth:200,justifyContent:'flex-end'}}>
          {procState==='processing'&&<div style={{display:'flex',alignItems:'center',gap:5,fontSize:10}}>
            <span className="pdot"/>
            <span style={{color:'var(--ac)',fontWeight:600,letterSpacing:'.06em'}}>LIVE</span>
          </div>}
          <div style={{display:'flex',alignItems:'center',gap:5,fontSize:10}}>
            {!apiOnline
              ?<><span style={{width:7,height:7,borderRadius:'50%',background:'var(--rd)',display:'inline-block'}}/>
                <span style={{color:'var(--rd)'}}>Offline</span></>
              :!modelReady
              ?<><div style={{width:7,height:7,border:'1.5px solid var(--yw)',borderTopColor:'transparent',
                  borderRadius:'50%'}} className="spin"/>
                <span style={{color:'var(--yw)'}}>Loading…</span></>
              :<><span style={{width:7,height:7,borderRadius:'50%',background:'var(--ac)',
                  display:'inline-block',animation:'pulse-a 2s infinite'}}/>
                <span style={{color:'var(--tx2)'}}>Ready</span></>
            }
          </div>
          <button className="btn-sm" onClick={()=>setDark(d=>!d)}>{dark?'☀':'☾'}</button>
        </div>
      </header>

      <div style={{flex:1,display:'grid',gridTemplateColumns:'300px 1fr 340px',
        gap:14,padding:14,overflow:'hidden',minHeight:0}}>
        <div style={{display:'flex',flexDirection:'column',gap:12,overflow:'hidden',minHeight:0}}>
          <UploadPanel state={uploadState} pct={uploadPct} onUpload={handleUpload} step={step} info={info}/>
          <FrameGallery frames={frames} selected={selFrame}
            onSelect={f=>{setSel(f);setLine(null);setStep(3)}}
            uploadState={uploadState} step={step}/>
        </div>
        <div style={{display:'flex',flexDirection:'column',overflow:'hidden',minHeight:0}}>
          <FrameCanvas frame={selFrame} onLineSaved={setLine}
            procState={procState} onProcess={handleProcess}
            step={step} progress={progress} modelReady={modelReady}
            liveImg={liveImg} liveDets={liveDets} isWarmup={isWarmup}/>
        </div>
        <div style={{overflowY:'auto',minHeight:0}}>
          <Analytics counters={counters} feed={feed}
            procState={procState} step={step} progress={progress}
            outputUrl={outputUrl} analytics={analytics}
            modelReady={modelReady} apiOnline={apiOnline}/>
        </div>
      </div>
    </div>
  )
}
