import { useState } from 'react'

const uuid = () =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36)
import { submitProductionEntry, submitAkpEntry, submitAttendanceEntry } from '../services/api'

type FormType = 'production' | 'akp' | 'attendance'

type CommonHeader = { report_date: string; site: string; department: string }

// ─── Production rows ────────────────────────────────────────────────────────

type ProdRow = {
  _id: string
  division: string
  luas_ha: string
  bbc_ton: string
  actual_today_ton: string
  actual_to_date_ton: string
  daily_target_ton: string
}

function emptyProd(): ProdRow {
  return { _id: uuid(), division: '', luas_ha: '', bbc_ton: '', actual_today_ton: '', actual_to_date_ton: '', daily_target_ton: '' }
}

// ─── AKP rows ───────────────────────────────────────────────────────────────

type AkpRow = {
  _id: string
  division: string
  blok: string
  luas_ha: string
  panen_kg: string
  jumlah_janjang: string
  akp_percent: string
  tk_panen: string
}

function emptyAkp(): AkpRow {
  return { _id: uuid(), division: '', blok: '', luas_ha: '', panen_kg: '', jumlah_janjang: '', akp_percent: '', tk_panen: '' }
}

// ─── Attendance rows ─────────────────────────────────────────────────────────

type AttRow = {
  _id: string
  worker_type: string
  afdeling: string
  actual_pemanen: string
  hadir: string
  ijin: string
  sakit: string
  cuti: string
  mangkir: string
}

function emptyAtt(): AttRow {
  return { _id: uuid(), worker_type: '', afdeling: '', actual_pemanen: '', hadir: '', ijin: '', sakit: '', cuti: '', mangkir: '' }
}

// ─── Utils ───────────────────────────────────────────────────────────────────

function n(s: string): number | null {
  const v = parseFloat(s)
  return isNaN(v) ? null : v
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function EntryPage() {
  const [formType, setFormType] = useState<FormType>('production')
  const [header, setHeader] = useState<CommonHeader>({ report_date: todayStr(), site: '', department: '农业' })
  const [prodRows, setProdRows] = useState<ProdRow[]>([emptyProd()])
  const [akpRows, setAkpRows] = useState<AkpRow[]>([emptyAkp()])
  const [attRows, setAttRows] = useState<AttRow[]>([emptyAtt()])
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  function setH<K extends keyof CommonHeader>(k: K, v: string) {
    setHeader(h => ({ ...h, [k]: v }))
  }

  async function handleSubmit() {
    setError('')
    setMessage('')
    if (!header.report_date || !header.site) { setError('请填写日期和园区'); return }
    setSaving(true)
    try {
      let result: { message: string }
      if (formType === 'production') {
        const rows = prodRows.filter(r => r.division.trim())
        if (rows.length === 0) { setError('至少填写一行数据（小区不能为空）'); return }
        result = await submitProductionEntry({
          report_date: header.report_date, site: header.site, department: header.department,
          rows: rows.map(r => ({
            division: r.division, luas_ha: n(r.luas_ha), bbc_ton: n(r.bbc_ton),
            actual_today_ton: n(r.actual_today_ton), actual_to_date_ton: n(r.actual_to_date_ton),
            daily_target_ton: n(r.daily_target_ton),
          })),
        })
      } else if (formType === 'akp') {
        const rows = akpRows.filter(r => r.division.trim())
        if (rows.length === 0) { setError('至少填写一行数据（小区不能为空）'); return }
        result = await submitAkpEntry({
          report_date: header.report_date, site: header.site, department: header.department,
          rows: rows.map(r => ({
            division: r.division, blok: r.blok, luas_ha: n(r.luas_ha),
            panen_kg: n(r.panen_kg), jumlah_janjang: n(r.jumlah_janjang),
            akp_percent: n(r.akp_percent), tk_panen: n(r.tk_panen),
          })),
        })
      } else {
        const rows = attRows.filter(r => r.worker_type.trim())
        if (rows.length === 0) { setError('至少填写一行数据（人员类型不能为空）'); return }
        result = await submitAttendanceEntry({
          report_date: header.report_date, site: header.site, department: header.department,
          rows: rows.map(r => ({
            worker_type: r.worker_type, afdeling: r.afdeling,
            actual_pemanen: n(r.actual_pemanen), hadir: n(r.hadir),
            ijin: n(r.ijin), sakit: n(r.sakit), cuti: n(r.cuti), mangkir: n(r.mangkir),
          })),
        })
      }
      setMessage(result.message)
      setTimeout(() => setMessage(''), 4000)
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="portal-page">
      <div className="page-title-section">
        <p className="page-eyebrow">数据采集</p>
        <h1>在线填报</h1>
        <p className="page-desc">直接录入日报数据，提交后实时写入数据仓库。数据以日期+园区+小区为主键，重复提交会覆盖。</p>
      </div>

      {/* 表单类型选择 */}
      <div className="entry-tabs">
        {([
          ['production', '产量监控日报'],
          ['akp', 'AKP 铲果密度'],
          ['attendance', '铲果工出勤'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={formType === key ? 'active' : ''}
            onClick={() => { setFormType(key); setError(''); setMessage('') }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* 公共表头 */}
      <div className="entry-header-card">
        <label className="field">
          <span>报表日期</span>
          <input type="date" value={header.report_date} onChange={e => setH('report_date', e.target.value)} />
        </label>
        <label className="field">
          <span>园区/工厂</span>
          <input placeholder="例如：七园" value={header.site} onChange={e => setH('site', e.target.value)} />
        </label>
        <label className="field">
          <span>部门</span>
          <select value={header.department} onChange={e => setH('department', e.target.value)}>
            <option value="农业">农业</option>
            <option value="工业">工业</option>
          </select>
        </label>
      </div>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-message">{message}</div>}

      {/* 产量监控日报 */}
      {formType === 'production' && (
        <EntryTable
          columns={[
            { key: 'division', label: '小区 *', width: 100 },
            { key: 'luas_ha', label: '面积(Ha)', width: 90 },
            { key: 'bbc_ton', label: '月目标BBC(吨)', width: 110 },
            { key: 'actual_today_ton', label: '当日产量(吨)', width: 110 },
            { key: 'actual_to_date_ton', label: '月累计(吨)', width: 100 },
            { key: 'daily_target_ton', label: '日目标(吨)', width: 100 },
          ]}
          rows={prodRows}
          onChange={setProdRows}
          onAdd={() => setProdRows(r => [...r, emptyProd()])}
          onRemove={(id) => setProdRows(r => r.filter(x => x._id !== id))}
        />
      )}

      {/* AKP 铲果密度 */}
      {formType === 'akp' && (
        <EntryTable
          columns={[
            { key: 'division', label: '小区 *', width: 90 },
            { key: 'blok', label: 'Blok', width: 80 },
            { key: 'luas_ha', label: 'Luas(Ha)', width: 85 },
            { key: 'panen_kg', label: 'Panen(Kg)', width: 95 },
            { key: 'jumlah_janjang', label: 'Janjang', width: 85 },
            { key: 'akp_percent', label: 'AKP%', width: 75 },
            { key: 'tk_panen', label: 'TK Panen', width: 80 },
          ]}
          rows={akpRows}
          onChange={setAkpRows}
          onAdd={() => setAkpRows(r => [...r, emptyAkp()])}
          onRemove={(id) => setAkpRows(r => r.filter(x => x._id !== id))}
        />
      )}

      {/* 出勤 */}
      {formType === 'attendance' && (
        <EntryTable
          columns={[
            { key: 'worker_type', label: '人员类型 *', width: 110, hint: 'harvester / maintenance' },
            { key: 'afdeling', label: '小区/Afdeling', width: 110 },
            { key: 'actual_pemanen', label: '实际人数', width: 85 },
            { key: 'hadir', label: '出勤', width: 70 },
            { key: 'ijin', label: '请假', width: 70 },
            { key: 'sakit', label: '病假', width: 70 },
            { key: 'cuti', label: '年假', width: 70 },
            { key: 'mangkir', label: '旷工', width: 70 },
          ]}
          rows={attRows}
          onChange={setAttRows}
          onAdd={() => setAttRows(r => [...r, emptyAtt()])}
          onRemove={(id) => setAttRows(r => r.filter(x => x._id !== id))}
        />
      )}

      <div className="entry-footer">
        <button className="btn-primary" type="button" disabled={saving} onClick={handleSubmit}>
          {saving ? '提交中...' : '提交到数据仓库'}
        </button>
        <span className="entry-hint">相同日期+园区+小区的数据会自动覆盖更新</span>
      </div>
    </section>
  )
}

// ─── Generic editable table ──────────────────────────────────────────────────

type ColDef = { key: string; label: string; width?: number; hint?: string }

function EntryTable<T extends Record<string, string> & { _id: string }>({
  columns, rows, onChange, onAdd, onRemove,
}: {
  columns: ColDef[]
  rows: T[]
  onChange: (rows: T[]) => void
  onAdd: () => void
  onRemove: (id: string) => void
}) {
  function updateCell(id: string, key: string, value: string) {
    onChange(rows.map(r => r._id === id ? { ...r, [key]: value } : r))
  }

  return (
    <div className="entry-table-card">
      <div className="entry-table-scroll">
        <table className="entry-table">
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col.key} style={{ minWidth: col.width ?? 80 }}>
                  {col.label}
                  {col.hint && <div className="entry-col-hint">{col.hint}</div>}
                </th>
              ))}
              <th style={{ width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row._id}>
                {columns.map(col => (
                  <td key={col.key}>
                    <input
                      className="entry-cell-input"
                      value={row[col.key] as string}
                      placeholder={col.key === 'worker_type' ? 'harvester' : ''}
                      onChange={e => updateCell(row._id, col.key, e.target.value)}
                    />
                  </td>
                ))}
                <td>
                  {rows.length > 1 && (
                    <button type="button" className="entry-remove-btn" onClick={() => onRemove(row._id)} title="删除行">×</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="entry-table-footer">
        <button type="button" className="btn-ghost" onClick={onAdd}>＋ 添加行</button>
        <span className="entry-hint">{rows.length} 行数据</span>
      </div>
    </div>
  )
}
