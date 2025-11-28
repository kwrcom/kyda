import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useParams, Link } from 'react-router-dom'

export default function AlertDetail(){
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    setLoading(true)
    axios.get(`/api/alerts/${encodeURIComponent(id)}`)
      .then(r=> setData(r.data))
      .finally(()=> setLoading(false))
  }, [id])

  if(loading) return <div style={{padding:20}}>Loading...</div>
  if(!data) return <div style={{padding:20}}>Not found</div>

  const path = data.detection_path || {}

  return (
    <div style={{padding:20}}>
      <h2>Transaction {data.transaction_id}</h2>
      <div><strong>Final verdict:</strong> {data.final_verdict}</div>
      <div><strong>Reason:</strong> {data.reason}</div>

      <h3>Detection path</h3>
      <pre style={{background:'#eee', padding:12}}>{JSON.stringify(path, null, 2)}</pre>

      <div style={{marginTop:20}}><Link to='/'>Back to Alerts</Link></div>
    </div>
  )
}
