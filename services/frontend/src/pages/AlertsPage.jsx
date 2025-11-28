import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'

export default function AlertsPage(){
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    setLoading(true)
    axios.get('/api/alerts/')
      .then(r=> setAlerts(r.data.alerts || []))
      .finally(()=> setLoading(false))
  }, [])

  const filtered = alerts.filter(a=>{
    if(filter === 'all') return true
    return a.detection_level === Number(filter)
  })

  return (
    <div style={{padding:20}}>
      <h2>Alerts</h2>
      <div style={{marginBottom:12}}>
        <label>Detection level filter: </label>
        <select value={filter} onChange={e=> setFilter(e.target.value)}>
          <option value='all'>All</option>
          <option value='0'>Level 0</option>
          <option value='1'>Level 1</option>
          <option value='2'>Level 2</option>
        </select>
      </div>

      {loading && <div>Loading...</div>}

      <table border='1' cellPadding='6' cellSpacing='0'>
        <thead>
          <tr>
            <th>ID</th>
            <th>Transaction ID</th>
            <th>Verdict</th>
            <th>Detection Level</th>
            <th>Reason</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(r=> (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{r.transaction_id}</td>
              <td>{r.final_verdict}</td>
              <td>{r.detection_level}</td>
              <td>{r.reason}</td>
              <td><Link to={`/alerts/${encodeURIComponent(r.transaction_id)}`}>View</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
