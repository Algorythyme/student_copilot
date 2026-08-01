import React, { useState, useEffect, useRef, useCallback } from 'react';
import { RevisionMode } from './RevisionMode';
import { AuthScreen } from './AuthScreen';
import { API_BASE, authHeaders, authHeadersMultipart, checkAuthExpiry } from './config';
import { logger } from './logger';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './index.css';

interface Profile {
  name: string;
  age: string;
  country: string;
  grade: string;
  learning_method?: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  attachmentName?: string;
}

interface SessionAttachment {
  id: string;
  filename: string;
  summary?: string;
  index?: number;
}

interface ConversationEntry {
  id: string;
  title: string;
  updated_at?: string;
}

interface RemoteMessage {
  role?: string;
  content?: string;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

const log = logger.context('StudentCopilotApp');

/** Returns a human-friendly relative timestamp like "2h ago" or "Mar 12". */
function formatRelativeTime(iso: string | undefined): string {
  if (!iso) return '';
  try {
    const date = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

function App() {
  // Auth
  const [currentUser, setCurrentUser] = useState<string | null>(localStorage.getItem('current_user'));

  // Navigation
  const [tab, setTab] = useState<'chat' | 'revision'>('chat');

  // Profile (hidden from default view)
  const [profile, setProfile] = useState<Profile>({ name: '', age: '', country: '', grade: '' });
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Chat state
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [attachments, setAttachments] = useState<SessionAttachment[]>([]);
  const [activeSubject, setActiveSubject] = useState('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const replaceTargetRef = useRef<string | null>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  // Chat history sidebar
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<ConversationEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [resumingConvId, setResumingConvId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevConvRef = useRef<string | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchAttachments = useCallback(async (targetConvId: string | null) => {
    if (!currentUser || !targetConvId || targetConvId.startsWith('notebook_temp_')) {
      setAttachments([]);
      return;
    }
    try {
      const headers = await authHeaders(currentUser);
      const res = await fetch(`${API_BASE}/conversations/${targetConvId}/attachments`, { headers });
      checkAuthExpiry(res);
      if (!res.ok) {
        setAttachments([]);
        return;
      }
      const data = await res.json();
      setAttachments(Array.isArray(data.attachments) ? data.attachments : []);
    } catch (err) {
      log.error('Failed to load attachments', { message: getErrorMessage(err, 'Unknown error') });
      setAttachments([]);
    }
  }, [currentUser]);

  useEffect(() => {
    if (!activeSubject.trim()) {
      void fetchAttachments(convId);
    } else {
      setAttachments([]);
    }
  }, [convId, activeSubject, fetchAttachments]);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  // Load profile on login
  useEffect(() => {
    if (!currentUser) return;
    (async () => {
      try {
        const headers = await authHeaders(currentUser);
        const res = await fetch(`${API_BASE}/users/me`, { headers });
        checkAuthExpiry(res);
        if (res.ok) {
          const data = await res.json();
          setProfile({
            name: data.full_name || '',
            age: data.age || '',
            country: data.country || '',
            grade: data.class_id || '',
            learning_method: data.learning_method || ''
          });
          log.info('Loaded learner profile', {
            hasProfile: Boolean(data.full_name || data.class_id),
          });
        }
      } catch (err) {
        log.error('Failed to load profile', { message: getErrorMessage(err, 'Unknown error') });
      }
    })();
  }, [currentUser]);

  // Fetch conversation list
  const fetchConversations = useCallback(async () => {
    if (!currentUser) return;
    try {
      const headers = await authHeaders(currentUser);
      const res = await fetch(`${API_BASE}/conversations`, { headers });
      checkAuthExpiry(res);
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
        log.debug('Loaded conversation history', {
          count: Array.isArray(data.conversations) ? data.conversations.length : 0,
        });
      }
    } catch (err) {
      log.error('Failed to load conversations', { message: getErrorMessage(err, 'Unknown error') });
    }
  }, [currentUser]);

  // Load conversations on login and when sidebar opens
  useEffect(() => {
    if (sidebarOpen && currentUser) {
      fetchConversations();
    }
  }, [sidebarOpen, currentUser, fetchConversations]);

  // Init conversation for chat mode
  useEffect(() => {
    if (!currentUser) return;
    if (tab !== 'chat' || activeSubject) return; // Only for general chat (no subject = general mode)
    if (convId) return;
    (async () => {
      try {
        const headers = await authHeaders(currentUser);
        const res = await fetch(`${API_BASE}/conversations/new`, {
          method: 'POST', headers, body: JSON.stringify({})
        });
        checkAuthExpiry(res);
        const data = await res.json();
        setConvId(data.conversation_id);
        log.info('Created conversation', { hasConversation: Boolean(data.conversation_id) });
      } catch (err) {
        log.error('Failed to create conversation', { message: getErrorMessage(err, 'Unknown error') });
      }
    })();
  }, [tab, currentUser, activeSubject, convId]);

  // Silent learning sync — end previous conversation in background
  const syncLearningProfile = async (convIdToEnd: string) => {
    if (!currentUser || convIdToEnd.startsWith('notebook_temp_')) return;
    try {
      const headers = await authHeaders(currentUser);
      const res = await fetch(`${API_BASE}/conversations/${convIdToEnd}/end`, {
        method: 'POST', headers
      });
      if (res.ok) {
        const data = await res.json();
        if (data.learning_method) {
          setProfile(prev => ({ ...prev, learning_method: data.learning_method }));
        }
      }
    } catch {
      return; // Silent: never block the user.
    }
  };

  // Sync on tab close / navigate away
  useEffect(() => {
    const handleUnload = () => {
      if (convId && currentUser && !convId.startsWith('notebook_temp_')) {
        const token = localStorage.getItem(`jwt_${currentUser}`);
        if (token) {
          navigator.sendBeacon(
            `${API_BASE}/conversations/${convId}/end`,
            new Blob([JSON.stringify({})], { type: 'application/json' })
          );
        }
      }
    };
    window.addEventListener('beforeunload', handleUnload);
    return () => window.removeEventListener('beforeunload', handleUnload);
  }, [convId, currentUser]);

  const handleNewChat = async () => {
    // Sync previous conversation silently
    if (convId) {
      prevConvRef.current = convId;
      syncLearningProfile(convId);
    }
    setMessages([]);
    setAttachments([]);
    setConvId(null);
    setActiveSubject('');
    setSidebarOpen(false);
    // New conversation will be created by useEffect
  };

  const handleRemoveAttachment = async (attachmentId: string) => {
    if (!currentUser || !convId) return;
    try {
      const headers = await authHeaders(currentUser);
      const res = await fetch(
        `${API_BASE}/conversations/${convId}/attachments/${encodeURIComponent(attachmentId)}`,
        { method: 'DELETE', headers }
      );
      checkAuthExpiry(res);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setAttachments(prev => prev.filter(a => a.id !== attachmentId));
      setToast({ message: 'Attachment removed.', type: 'success' });
    } catch (err: unknown) {
      setToast({ message: getErrorMessage(err, 'Could not remove attachment'), type: 'error' });
    }
  };

  const handleReplaceAttachment = (attachmentId: string) => {
    replaceTargetRef.current = attachmentId;
    replaceInputRef.current?.click();
  };

  // Resume a prior conversation
  const handleResumeConversation = async (targetConvId: string) => {
    if (!currentUser || targetConvId === convId) {
      setSidebarOpen(false);
      return;
    }

    // Sync current conversation silently before switching
    if (convId) {
      syncLearningProfile(convId);
    }

    setResumingConvId(targetConvId);
    setLoadingHistory(true);

    try {
      const headers = await authHeaders(currentUser);
      const res = await fetch(`${API_BASE}/conversations/${targetConvId}/messages`, { headers });
      checkAuthExpiry(res);

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      const loadedMessages: Message[] = (data.messages || []).map((m: RemoteMessage) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content || '',
      }));

      setMessages(loadedMessages);
      setConvId(targetConvId);
      setActiveSubject('');
      setSidebarOpen(false);
      await fetchAttachments(targetConvId);
      log.info('Resumed conversation', { messageCount: loadedMessages.length });
    } catch (err: unknown) {
      log.error('Failed to resume conversation', { message: getErrorMessage(err, 'Unknown error') });
      setToast({ message: `Failed to load chat: ${getErrorMessage(err, 'Unknown error')}`, type: 'error' });
    } finally {
      setLoadingHistory(false);
      setResumingConvId(null);
    }
  };

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || loading) return;

    const isNotebook = !!activeSubject.trim();

    if (!isNotebook && !convId) return;

    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      const endpoint = isNotebook ? `${API_BASE}/notebook/ask` : `${API_BASE}/chat`;
      const body = isNotebook
        ? { question: userMsg, active_subject: activeSubject, active_class: profile.grade }
        : {
            conversation_id: convId,
            message: userMsg,
            user_profile: {
              full_name: profile.name, age: profile.age,
              country: profile.country, class_id: profile.grade
            }
          };

      const headers = await authHeaders(currentUser!);
      const res = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(body) });
      checkAuthExpiry(res);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply || data.answer }]);
      log.debug('Chat response received', { isNotebook });
    } catch (err: unknown) {
      log.error('Chat request failed', { isNotebook, message: getErrorMessage(err, 'Unknown error') });
      setMessages(prev => [...prev, { role: 'assistant', content: `Something went wrong: ${getErrorMessage(err, 'Unknown error')}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const selectedFile = e.target.files[0];
    const isNotebook = !!activeSubject.trim();
    const replaceId = replaceTargetRef.current;
    replaceTargetRef.current = null;

    if (!isNotebook && !convId) return;
    setUploading(true);

    const formData = new FormData();
    formData.append('file', selectedFile);
    if (isNotebook) {
      formData.append('subject', activeSubject || 'General');
      formData.append('class_id', profile.grade || 'General');
    }

    try {
      if (!isNotebook && replaceId && convId) {
        const headers = await authHeaders(currentUser!);
        await fetch(
          `${API_BASE}/conversations/${convId}/attachments/${encodeURIComponent(replaceId)}`,
          { method: 'DELETE', headers }
        );
      }

      const endpoint = isNotebook
        ? `${API_BASE}/notebook/upload`
        : `${API_BASE}/upload?conversation_id=${convId}`;
      const headers = await authHeadersMultipart(currentUser!);
      const res = await fetch(endpoint, { method: 'POST', headers, body: formData });
      checkAuthExpiry(res);
      const data = await res.json();
      if (isNotebook && data.chunks) {
        log.info('Notebook upload processed', { chunks: Number(data.chunks) || 0 });
        setToast({ message: `${selectedFile.name} processed — ${data.chunks} study sections created.`, type: 'success' });
      } else if (data.summary || data.id) {
        log.info('Chat upload processed', { hasSummary: true });
        setMessages(prev => [
          ...prev,
          { role: 'user', content: selectedFile.name, attachmentName: selectedFile.name },
          {
            role: 'assistant',
            content: replaceId
              ? `I've replaced the previous file with "${selectedFile.name}". Ask me about it when you're ready.`
              : `I've received "${selectedFile.name}". Ask me a question about it when you're ready.`,
          },
        ]);
        await fetchAttachments(convId);
        setToast({
          message: replaceId ? 'Attachment replaced.' : 'File uploaded successfully.',
          type: 'success',
        });
      }
    } catch (err) {
      log.error('Upload failed', { isNotebook, message: getErrorMessage(err, 'Unknown error') });
      setToast({ message: 'Upload failed. Please try again.', type: 'error' });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleLogout = () => {
    // Sync before logout
    if (convId) syncLearningProfile(convId);
    localStorage.removeItem('current_user');
    if (currentUser) localStorage.removeItem(`jwt_${currentUser}`);
    setCurrentUser(null);
    setConvId(null);
    setMessages([]);
    setProfile({ name: '', age: '', country: '', grade: '' });
    setConversations([]);
    setSidebarOpen(false);
    log.info('User logged out');
  };

  // ─── Auth Gate ───────────────────────────────────────────
  if (!currentUser) {
    return <AuthScreen onLogin={setCurrentUser} />;
  }

  // ─── Student Layout ──────────────────────────────────────
  const isNotebookMode = !!activeSubject.trim();

  return (
    <>
      <nav className="top-nav">
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          title={sidebarOpen ? 'Close chat history' : 'Open chat history'}
          aria-label="Toggle chat history"
        >
          <span className="sidebar-toggle-icon">{sidebarOpen ? '✕' : '☰'}</span>
        </button>
        <span className="nav-brand">Student Copilot</span>
        <div className="nav-tabs">
          <button className={`nav-tab ${tab === 'chat' ? 'active' : ''}`} onClick={() => setTab('chat')}>Chat</button>
          <button className={`nav-tab ${tab === 'revision' ? 'active' : ''}`} onClick={() => setTab('revision')}>Revision</button>
        </div>
        <div className="nav-actions">
          {tab === 'chat' && (
            <button className="btn-ghost" onClick={handleNewChat} style={{ fontSize: '0.78rem', padding: '0.45rem 0.75rem' }}>
              + New Chat
            </button>
          )}
          <button className="nav-icon-btn" onClick={() => setSettingsOpen(true)} title="Settings">⚙</button>
          <button className="btn-danger" onClick={handleLogout}>Logout</button>
        </div>
      </nav>

      <div className="app-body">
        {/* ─── Chat History Sidebar ─── */}
        <aside className={`history-sidebar ${sidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-header">
            <h3>Chat History</h3>
            <button className="btn-ghost sidebar-new-btn" onClick={handleNewChat}>+ New</button>
          </div>
          <div className="sidebar-list">
            {conversations.length === 0 ? (
              <div className="sidebar-empty">
                <p>No previous chats yet.</p>
                <p className="sidebar-empty-sub">Start a conversation and it will appear here.</p>
              </div>
            ) : (
              conversations.map(c => (
                <button
                  key={c.id}
                  className={`sidebar-item ${c.id === convId ? 'active' : ''} ${resumingConvId === c.id ? 'loading' : ''}`}
                  onClick={() => handleResumeConversation(c.id)}
                  disabled={loadingHistory}
                  title={c.title}
                >
                  <span className="sidebar-item-title">{c.title || 'Untitled Chat'}</span>
                  <span className="sidebar-item-time">{formatRelativeTime(c.updated_at)}</span>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* Backdrop for mobile */}
        {sidebarOpen && <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />}

        <div className="content-area">
          {tab === 'revision' ? (
            <RevisionMode userId={currentUser} />
          ) : (
            <>
              {/* Chat toolbar — subject selector */}
              <div className="chat-toolbar">
                <input
                  className="subject-select"
                  type="text"
                  placeholder="Subject (optional)"
                  value={activeSubject}
                  onChange={e => setActiveSubject(e.target.value)}
                />
                <span className="chat-mode-label">
                  {isNotebookMode
                    ? `Studying ${activeSubject} from your materials`
                    : 'General tutor — ask anything'}
                </span>
              </div>

              {!isNotebookMode && attachments.length > 0 && (
                <div className="attachment-chip-row">
                  {attachments.map(file => (
                    <div key={file.id} className="attachment-chip" title={file.summary || file.filename}>
                      <span className="attachment-chip-name">📎 {file.filename}</span>
                      <button
                        type="button"
                        className="attachment-chip-btn"
                        title="Replace"
                        disabled={uploading}
                        onClick={() => handleReplaceAttachment(file.id)}
                      >
                        ↻
                      </button>
                      <button
                        type="button"
                        className="attachment-chip-btn danger"
                        title="Remove"
                        disabled={uploading}
                        onClick={() => void handleRemoveAttachment(file.id)}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Messages */}
              <div className="chat-messages">
                {messages.length === 0 && (
                  <div className="chat-empty">
                    <h3>{profile.name ? `Hi ${profile.name.split(' ')[0]}!` : 'Welcome!'}</h3>
                    <p>
                      {isNotebookMode
                        ? `Ask me anything about ${activeSubject}. I'll answer from your study materials.`
                        : 'What would you like to study today? Type a subject above to study from your materials, or just ask me anything.'}
                    </p>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`message ${m.role}`}>
                    {m.attachmentName ? (
                      <span className="attachment-chip inline">📎 {m.attachmentName}</span>
                    ) : null}
                    {m.role === 'user' ? (
                      m.attachmentName ? null : m.content
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkMath, remarkGfm]} rehypePlugins={[rehypeKatex]}>
                        {m.content}
                      </ReactMarkdown>
                    )}
                  </div>
                ))}
                {loading && (
                  <div className="message assistant" style={{ opacity: 0.6 }}>Thinking...</div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input bar */}
              <form className="chat-input-bar" onSubmit={handleSend}>
                <div className="btn-upload-icon" title={uploading ? 'Uploading...' : 'Upload file'}>
                  {uploading ? '⏳' : '📎'}
                  <input type="file" onChange={handleUpload} disabled={uploading || (!isNotebookMode && !convId)} />
                </div>
                <input
                  ref={replaceInputRef}
                  type="file"
                  style={{ display: 'none' }}
                  onChange={handleUpload}
                  disabled={uploading || (!isNotebookMode && !convId)}
                />
                <input
                  type="text"
                  placeholder="Ask me anything..."
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  disabled={loading || (!isNotebookMode && !convId)}
                />
                <button type="submit" className="btn-send" disabled={loading || !input.trim() || (!isNotebookMode && !convId)}>
                  Send
                </button>
              </form>
            </>
          )}
        </div>
      </div>

      {settingsOpen && <SettingsModal profile={profile} onClose={() => setSettingsOpen(false)} />}

      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
          <button className="toast-close" onClick={() => setToast(null)}>×</button>
        </div>
      )}
    </>
  );
}

// ─── Settings Modal ─────────────────────────────────────────
function SettingsModal({ profile, onClose }: { profile: Profile; onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-body" onClick={e => e.stopPropagation()}>
        <h2>Settings</h2>

        <div className="field">
          <label>Name</label>
          <input type="text" value={profile.name} readOnly />
        </div>
        <div className="field-row">
          <div className="field">
            <label>Age</label>
            <input type="text" value={profile.age || '—'} readOnly />
          </div>
          <div className="field">
            <label>Country</label>
            <input type="text" value={profile.country || '—'} readOnly />
          </div>
        </div>
        <div className="field">
          <label>Class</label>
          <input type="text" value={profile.grade || '—'} readOnly />
        </div>

        {profile.learning_method && (
          <div className="field">
            <label>Identified Learning Style</label>
            <textarea readOnly value={profile.learning_method} rows={4} style={{ opacity: 0.8, resize: 'none' }} />
          </div>
        )}

        <button className="btn-primary" onClick={onClose} style={{ marginTop: '0.5rem' }}>Close</button>
      </div>
    </div>
  );
}

export default App;
