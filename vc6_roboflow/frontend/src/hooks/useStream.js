import{useEffect,useRef}from'react'
import{openStream}from'../utils/api'
export function useStream({jobId,active,onFrame,onCrossing,onDone,onError}){
  const ref=useRef(null)
  useEffect(()=>{
    if(!active||!jobId){ref.current?.();ref.current=null;return}
    ref.current=openStream(jobId,{onFrame,onCrossing,onDone,onError})
    return()=>{ref.current?.();ref.current=null}
  },[active,jobId])
}
