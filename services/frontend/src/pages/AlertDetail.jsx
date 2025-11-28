import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { useParams, Link } from 'react-router-dom'

export default function AlertDetail() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    axios.get(`/api/alerts/${encodeURIComponent(id)}`)
      .then(r => setData(r.data))
      .catch(err => console.error("Failed to fetch alert detail", err))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="container" style={{ paddingTop: '4rem', textAlign: 'center' }}>Loading details...</div>
  if (!data) return <div className="container" style={{ paddingTop: '4rem', textAlign: 'center' }}>Transaction not found</div>

  const path = data.detection_path || {}

  return (
    <div className="container">
      <div style={{ marginBottom: '2rem' }}>
        <Link to="/" style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          ← Back to Dashboard
        </Link>
      </div>

      <div className="card">
        <header style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: '0 0 0.5rem 0' }}>Transaction Details</h1>
              <p className="font-mono" style={{ color: 'var(--text-secondary)', margin: 0 }}>ID: {data.transaction_id}</p>
            </div>
            <div>
              {data.detection_level === 2 && <span className="badge badge-danger" style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>Fraud Detected</span>}
              {data.detection_level === 1 && <span className="badge badge-warning" style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>Suspicious</span>}
              {data.detection_level === 0 && <span className="badge badge-success" style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>Safe</span>}
            </div>
          </div>
        </header>

        <div className="grid-cols-3" style={{ marginBottom: '2rem' }}>
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Final Verdict</p>
            <p style={{ fontWeight: '600', fontSize: '1.125rem', margin: 0 }}>{data.final_verdict}</p>
          </div>
          <div style={{ gridColumn: 'span 2' }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Reason</p>
            <p style={{ margin: 0 }}>{data.reason}</p>
          </div>
        </div>

        <div>
          <h3 style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>Detection Path Analysis</h3>
          <div style={{ backgroundColor: '#f8fafc', padding: '1.5rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <pre style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-primary)', overflowX: 'auto' }}>
              {JSON.stringify(path, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
