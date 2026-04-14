import React, { useState } from 'react';
import { API_BASE, authHeaders } from './config';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface Question {
    id: string;
    type: 'mcq' | 'theory';
    text: string;
    options?: string[];
    correct_answer?: string;
}

interface RevisionModeProps {
    userId: string;
}

export const RevisionMode: React.FC<RevisionModeProps> = ({ userId }) => {
    const [step, setStep] = useState<'config' | 'exam' | 'result'>('config');
    const [config, setConfig] = useState({
        classId: '',
        subject: '',
        topics: '',
        mcqCount: 5,
        theoryCount: 2
    });
    const [questions, setQuestions] = useState<Question[]>([]);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(false);
    const [feedback, setFeedback] = useState<string>('');
    const [error, setError] = useState<string>('');

    const resetSession = () => {
        setStep('config');
        setQuestions([]);
        setAnswers({});
        setFeedback('');
        setError('');
    };

    const handleCountChange = (field: 'mcqCount' | 'theoryCount', value: string) => {
        const parsed = parseInt(value);
        // Guard against NaN — clamp to 0 minimum, 20 maximum
        const clamped = isNaN(parsed) ? 0 : Math.max(0, Math.min(20, parsed));
        setConfig({ ...config, [field]: clamped });
    };

    const startExam = async () => {
        if (!config.subject.trim()) return alert('Please enter a subject');
        if (!config.classId.trim()) return alert('Please enter a class id');
        if (config.mcqCount + config.theoryCount === 0) return alert('Set at least 1 question');
        setLoading(true);
        setError('');
        try {
            const headers = await authHeaders(userId);
            const res = await fetch(`${API_BASE}/revision/generate`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    class_id: config.classId,
                    subject: config.subject,
                    topics: config.topics || undefined,
                    mcq_count: config.mcqCount,
                    theory_count: config.theoryCount
                })
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(errData.detail || `HTTP ${res.status}`);
            }
            const data = await res.json();
            const qs = data.questions || [];
            if (qs.length === 0) {
                throw new Error('No questions were generated. Ensure teaching materials exist for this subject.');
            }
            setQuestions(qs);
            setAnswers({});
            setStep('exam');
        } catch (err: any) {
            setError(err.message || 'Failed to generate exam.');
        } finally {
            setLoading(false);
        }
    };

    const submitExam = async () => {
        // Validate: at least answer some questions
        const answered = Object.keys(answers).filter(k => answers[k].trim()).length;
        if (answered === 0) return alert('Please answer at least one question before submitting.');

        setLoading(true);
        setError('');
        try {
            const headers = await authHeaders(userId);
            const res = await fetch(`${API_BASE}/revision/evaluate`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    class_id: config.classId,
                    subject: config.subject,
                    questions: questions,
                    answers: answers
                })
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(errData.detail || `HTTP ${res.status}`);
            }
            const data = await res.json();
            setFeedback(data.feedback);
            setStep('result');
        } catch (err: any) {
            setError(err.message || 'Evaluation failed.');
        } finally {
            setLoading(false);
        }
    };

    if (step === 'config') {
        return (
            <div className="revision-config">
                <h2>Sovereign Assessment Setup</h2>
                {error && <div style={{ color: '#ef4444', padding: '1rem', background: 'rgba(239,68,68,0.1)', borderRadius: '8px', marginBottom: '1rem' }}>{error}</div>}
                <div className="portal-form">
                    <div className="form-group">
                        <label>Class ID</label>
                        <input value={config.classId} onChange={e => setConfig({...config, classId: e.target.value})} placeholder="e.g. Grade_10" />
                    </div>
                    <div className="form-group">
                        <label>Subject Focus</label>
                        <input value={config.subject} onChange={e => setConfig({...config, subject: e.target.value})} placeholder="e.g. Biology" />
                    </div>
                    <div className="form-group">
                        <label>Specific Topics (Optional)</label>
                        <input value={config.topics} onChange={e => setConfig({...config, topics: e.target.value})} placeholder="e.g. Cell Division, Mitosis" />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem' }}>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label>MCQ Count</label>
                            <input type="number" min="0" max="20" value={config.mcqCount} onChange={e => handleCountChange('mcqCount', e.target.value)} />
                        </div>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label>Theory Count</label>
                            <input type="number" min="0" max="20" value={config.theoryCount} onChange={e => handleCountChange('theoryCount', e.target.value)} />
                        </div>
                    </div>
                    <button onClick={startExam} className="btn-primary" disabled={loading}>
                        {loading ? 'Analyzing Vectors & Generating Exam...' : 'Initialize Revision Session'}
                    </button>
                </div>
            </div>
        );
    }

    if (step === 'exam') {
        return (
            <div className="revision-exam">
                <header>
                    <h2>Revision Exam: {config.subject}</h2>
                    <p>{questions.length} Questions Targeted • {Object.keys(answers).filter(k => answers[k]?.trim()).length} Answered</p>
                </header>
                {error && <div style={{ color: '#ef4444', padding: '1rem', background: 'rgba(239,68,68,0.1)', borderRadius: '8px', marginBottom: '1rem' }}>{error}</div>}
                <div className="questions-list">
                    {questions.map((q, idx) => (
                        <div key={q.id} className="question-card">
                            <span className="q-badge">{q.type.toUpperCase()}</span>
                            <p className="q-text">{idx+1}. {q.text}</p>
                            {q.type === 'mcq' ? (
                                <div className="options-grid">
                                    {q.options?.map(opt => (
                                        <label key={opt} className={`option-label ${answers[q.id] === opt ? 'active' : ''}`}>
                                            <input 
                                                type="radio" 
                                                name={q.id} 
                                                value={opt} 
                                                checked={answers[q.id] === opt}
                                                onChange={e => setAnswers({...answers, [q.id]: e.target.value})}
                                            />
                                            {opt}
                                        </label>
                                    ))}
                                </div>
                            ) : (
                                <textarea 
                                    placeholder="Explain your answer in detail..."
                                    value={answers[q.id] || ''}
                                    onChange={e => setAnswers({...answers, [q.id]: e.target.value})}
                                    rows={4}
                                />
                            )}
                        </div>
                    ))}
                </div>
                <button onClick={submitExam} className="btn-primary" style={{ marginTop: '2rem' }} disabled={loading}>
                    {loading ? 'Grading using Sovereignty...' : 'Submit to Oracle for Evaluation'}
                </button>
            </div>
        );
    }

    return (
        <div className="revision-result">
            <h2>Evaluation Report</h2>
            <div 
                className="feedback-content" 
                style={{ lineHeight: '1.7', fontSize: '1.05rem', marginTop: '1rem' }}
            >
                {feedback ? (
                    <ReactMarkdown
                        remarkPlugins={[remarkMath, remarkGfm]}
                        rehypePlugins={[rehypeKatex]}
                    >
                        {feedback}
                    </ReactMarkdown>
                ) : null}
            </div>
            <button onClick={resetSession} className="btn-secondary" style={{ marginTop: '2rem' }}>
                New Revision Session
            </button>
        </div>
    );
};
