import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { Link } from 'react-router-dom'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    axios.get('/api/alerts/')
      .then(r => setAlerts(r.data.alerts || []))
      .catch(err => console.error("Failed to fetch alerts", err))
      .finally(() => setLoading(false))
  }, [])

  const filtered = alerts.filter(a => {
    if (filter === 'all') return true
    return a.detection_level === Number(filter)
  })

  // Calculate Stats
  const totalAlerts = alerts.length
  const highRisk = alerts.filter(a => a.detection_level === 2).length
  const suspicious = alerts.filter(a => a.detection_level === 1).length
  const safe = alerts.filter(a => a.detection_level === 0).length

  return (
    <div className="container">
      {/* Header */}
      <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: 0 }}>KYDA Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', margin: '0.25rem 0 0' }}>Real-time Fraud Detection System</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <div className="badge badge-neutral">v1.0.0</div>
          <div className="badge badge-success">System Online</div>
        </div>
      </header>

      {/* Stats Cards */}
      <div className="grid-cols-3" style={{ marginBottom: '2rem' }}>
        <div className="card">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>Total Transactions</p>
          <h2 style={{ fontSize: '2rem', fontWeight: '700', margin: 0 }}>{totalAlerts}</h2>
          <p style={{ fontSize: '0.75rem', color: 'var(--success-color)', marginTop: '0.5rem' }}>+12% from last hour</p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>High Risk Alerts</p>
          <h2 style={{ fontSize: '2rem', fontWeight: '700', margin: 0, color: 'var(--danger-color)' }}>{highRisk}</h2>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>Requires immediate attention</p>
        </div>
        <div className="card">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>System Health</p>
          <h2 style={{ fontSize: '2rem', fontWeight: '700', margin: 0, color: 'var(--accent-color)' }}>99.9%</h2>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>All services operational</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Toolbar */}
        <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '1.125rem' }}>Recent Activity</h3>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Filter:</span>
            <select 
              value={filter} 
              onChange={e => setFilter(e.target.value)}
              style={{ 
                padding: '0.5rem', 
                borderRadius: 'var(--radius-md)', 
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-app)',
                fontSize: '0.875rem'
              }}
            >
              <option value='all'>All Transactions</option>
              <option value='2'>High Risk (Level 2)</option>
              <option value='1'>Suspicious (Level 1)</option>
              <option value='0'>Safe (Level 0)</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="table-container" style={{ border: 'none', borderRadius: 0 }}>
          {loading ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              Loading transactions...
            </div>
          ) : (
            <table cellSpacing='0'>
              <thead>
                <tr>
                  <th>Transaction ID</th>
                  <th>Status</th>
                  <th>Risk Score</th>
                  <th>Reason</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                      No transactions found matching filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map(r => (
                    <tr key={r.id}>
                      <td className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                        {r.transaction_id.substring(0, 18)}...
                      </td>
                      <td>
                        {r.detection_level === 2 && <span className="badge badge-danger">Fraud</span>}
                        {r.detection_level === 1 && <span className="badge badge-warning">Suspicious</span>}
                        {r.detection_level === 0 && <span className="badge badge-success">Safe</span>}
                      </td>
                      <td style={{ fontWeight: '600' }}>
                        {/* Mocking a score based on level for visual demo */}
                        {r.detection_level === 2 ? '0.98' : r.detection_level === 1 ? '0.65' : '0.12'}
                      </td>
                      <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {r.reason || 'No anomalies detected'}
                      </td>
                      <td>
                        <Link to={`/alerts/${encodeURIComponent(r.transaction_id)}`} className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem' }}>
                          Details
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
