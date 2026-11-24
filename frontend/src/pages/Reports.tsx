import React, { useCallback, useEffect, useState } from 'react';
import { downloadReport, generateReport, getReports } from '../services/reportService';
import { useFieldContext } from '../context/FieldContext';

interface ReportItem {
  id: number;
  field_id: number;
  title: string;
  report_type: string;
  created_at: string;
}

const Reports: React.FC = () => {
  const { selectedFieldId } = useFieldContext();
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await getReports(selectedFieldId);
      setReports(res.data || []);
    } catch (err) {
      console.error('Failed to fetch reports:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedFieldId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await generateReport(selectedFieldId, { report_type: 'field_summary' });
      await load();
    } catch (err) {
      console.error('Failed to generate report:', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (id: number, title: string) => {
    try {
      const res = await downloadReport(id);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download report:', err);
    }
  };

  return (
    <div>
      <h2>Generate Reports</h2>
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
          {generating ? '⏳ Building PDF...' : '📄 Generate PDF Report'}
        </button>

        <div style={{ marginTop: '2rem' }}>
          <h3>Recent Reports ({reports.length})</h3>
          {loading ? (
            <p>Loading reports...</p>
          ) : reports.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
              No reports available yet. Click <strong>Generate PDF Report</strong> above.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {reports.map((r) => (
                <div
                  key={r.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.75rem 1rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                    backgroundColor: 'var(--bg-secondary)',
                  }}
                >
                  <div>
                    <strong>{r.title}</strong>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      Created: {new Date(r.created_at).toLocaleString()}
                    </div>
                  </div>
                  <button className="btn btn-primary" onClick={() => handleDownload(r.id, r.title)}>
                    ⬇️ Download PDF
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Reports;
