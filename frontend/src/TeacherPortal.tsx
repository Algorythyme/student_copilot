import React, { useState } from 'react';
import { API_BASE, authHeadersMultipart } from './config';

export const TeacherPortal: React.FC<{ userId: string }> = ({ userId }) => {
    // Separate state for each form — fixes M1 shared classId bug
    const [uploadClassId, setUploadClassId] = useState('');
    const [uploadSubject, setUploadSubject] = useState('');
    const [file, setFile] = useState<File | null>(null);

    const [status, setStatus] = useState<{message: string, type: 'success' | 'error' | 'info'} | null>(null);
    const [loading, setLoading] = useState(false);

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file || !uploadClassId || !uploadSubject) {
            setStatus({ message: 'Missing fields for global ingestion.', type: 'error' });
            return;
        }

        setLoading(true);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('class_id', uploadClassId);
        formData.append('subject', uploadSubject);

        try {
            const headers = await authHeadersMultipart(userId);
            const res = await fetch(`${API_BASE}/teacher/upload`, {
                method: 'POST',
                headers: headers,
                body: formData
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({ detail: 'Upload failed' }));
                throw new Error(errData.detail || `HTTP ${res.status}`);
            }
            const data = await res.json();
            setStatus({ message: `Success: Ingested ${data.chunks} chunks into ${uploadClassId}:${uploadSubject}`, type: 'success' });
        } catch (err: any) {
            setStatus({ message: err.message || 'Upload failed.', type: 'error' });
        } finally {
            setLoading(false);
        }
    };



    return (
        <div className="teacher-portal">
            <header className="portal-header">
                <h1>Knowledge Curation Portal</h1>
                <p className="subtitle">Sovereign Administrative Interface</p>
            </header>

            <div className="portal-grid">
                {/* Global Knowledge Ingestion */}
                <section className="portal-card">
                    <h2>Global Knowledge Ingestion</h2>
                    <p>Upload textbooks or syllabi to be shared across a class cohort.</p>
                    <form onSubmit={handleUpload} className="portal-form">
                        <div className="form-group">
                            <label>Class Cohort ID (e.g. Grade_10)</label>
                            <input value={uploadClassId} onChange={e => setUploadClassId(e.target.value)} placeholder="Grade_10" />
                        </div>
                        <div className="form-group">
                            <label>Subject Domain</label>
                            <input value={uploadSubject} onChange={e => setUploadSubject(e.target.value)} placeholder="Biology" />
                        </div>
                        <div className="form-group">
                            <label>Source Document</label>
                            <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
                        </div>
                        <button type="submit" className="btn-primary" disabled={loading}>
                            {loading ? 'Ingesting...' : 'Ingest to Global Index'}
                        </button>
                    </form>
                </section>


            </div>

            {status && (
                <div className={`status-toast ${status.type}`}>
                    {status.message}
                    <button onClick={() => setStatus(null)}>×</button>
                </div>
            )}

            <style>{`
                .teacher-portal {
                    padding: 2rem;
                    max-width: 1200px;
                    margin: 0 auto;
                    color: var(--text);
                }
                .portal-header {
                    margin-bottom: 3rem;
                    text-align: center;
                }
                .portal-header h1 {
                    font-size: 2.5rem;
                    background: linear-gradient(45deg, var(--accent), #a855f7);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin: 0;
                }
                .subtitle {
                    color: var(--text-dim);
                    letter-spacing: 2px;
                    text-transform: uppercase;
                    font-size: 0.8rem;
                }
                .portal-grid {
                    display: grid;
                    grid-template-columns: 1fr;
                    max-width: 600px;
                    margin: 0 auto;
                    gap: 2rem;
                }
                .portal-card {
                    background: var(--bg-card);
                    border: 1px solid var(--border);
                    padding: 2rem;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                }
                .portal-card h2 {
                    margin-top: 0;
                    color: var(--accent);
                }
                .portal-card p {
                    color: var(--text-dim);
                    font-size: 0.9rem;
                    margin-bottom: 1.5rem;
                }
                .portal-form {
                    display: flex;
                    flex-direction: column;
                    gap: 1.2rem;
                }
                .form-group label {
                    display: block;
                    font-size: 0.8rem;
                    margin-bottom: 0.4rem;
                    color: var(--text-dim);
                }
                .form-group input {
                    width: 100%;
                    padding: 0.8rem;
                    background: var(--bg);
                    border: 1px solid var(--border);
                    color: var(--text);
                    border-radius: 6px;
                }
                .btn-primary {
                    background: var(--accent);
                    color: white;
                    border: none;
                    padding: 1rem;
                    border-radius: 6px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .btn-secondary {
                    background: transparent;
                    color: var(--accent);
                    border: 1px solid var(--accent);
                    padding: 1rem;
                    border-radius: 6px;
                    font-weight: bold;
                    cursor: pointer;
                }
                .status-toast {
                    position: fixed;
                    bottom: 2rem;
                    right: 2rem;
                    padding: 1rem 2rem;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                    animation: slideUp 0.3s ease-out;
                }
                .status-toast.success { background: #10b981; color: white; }
                .status-toast.error { background: #ef4444; color: white; }
                @keyframes slideUp {
                    from { transform: translateY(100%); opacity: 0; }
                    to { transform: translateY(0); opacity: 1; }
                }
            `}</style>
        </div>
    );
};
