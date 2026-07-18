import React, { useState } from 'react';
import { API_BASE } from './config';
import { getSupabase, isSupabaseConfigured } from './supabase';

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

interface AuthProps {
  onLogin: (userId: string) => void;
}

export const AuthScreen: React.FC<AuthProps> = ({ onLogin }) => {
  const useSupabase = isSupabaseConfigured();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [age, setAge] = useState('');
  const [country, setCountry] = useState('');
  const [classId, setClassId] = useState('');
  const [subjects, setSubjects] = useState('');

  const handleSupabaseAuth = async () => {
    const supabase = getSupabase();
    if (mode === 'login') {
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (authError) {
        throw new Error(authError.message);
      }
      const userId = data.user?.id;
      if (!userId) {
        throw new Error('Sign in succeeded but no user id was returned.');
      }
      localStorage.setItem('current_user', userId);
      onLogin(userId);
      return;
    }

    const { data, error: authError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
          age: age ? parseInt(age, 10) : null,
          country,
          class_id: classId,
          subjects,
        },
      },
    });
    if (authError) {
      throw new Error(authError.message);
    }
    const userId = data.user?.id;
    if (!userId) {
      throw new Error('Registration succeeded but no user id was returned.');
    }
    localStorage.setItem('current_user', userId);
    onLogin(userId);
  };

  const handleLegacyAuth = async () => {
    if (mode === 'login') {
      const res = await fetch(`${API_BASE}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(err.detail || 'Invalid credentials');
      }
      const data = await res.json();
      localStorage.setItem(`jwt_${data.user_id}`, data.access_token);
      localStorage.setItem('current_user', data.user_id);
      onLogin(data.user_id);
      return;
    }

    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        role: 'student',
        full_name: fullName,
        age: age ? parseInt(age, 10) : null,
        country,
        class_id: classId,
        subjects,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
      throw new Error(err.detail || 'Failed to create account');
    }
    const data = await res.json();
    localStorage.setItem(`jwt_${data.user_id}`, data.access_token);
    localStorage.setItem('current_user', data.user_id);
    onLogin(data.user_id);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (useSupabase) {
        await handleSupabaseAuth();
      } else {
        await handleLegacyAuth();
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Authentication failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Student Copilot</h1>
        <p className="subtitle">Your AI-powered study partner</p>
        {useSupabase && (
          <p className="subtitle">Web demo — Supabase Auth</p>
        )}

        <div className="auth-tabs">
          <button className={`auth-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')} type="button">
            Sign In
          </button>
          <button className={`auth-tab ${mode === 'register' ? 'active' : ''}`} onClick={() => setMode('register')} type="button">
            Create Account
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {useSupabase ? (
            <div className="field">
              <label>Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
          ) : (
            <div className="field">
              <label>Username</label>
              <input type="text" required value={username} onChange={e => setUsername(e.target.value)} placeholder="e.g. johndoe" />
            </div>
          )}
          <div className="field">
            <label>Password</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
          </div>

          {mode === 'register' && (
            <>
              <div className="field">
                <label>Full Name</label>
                <input type="text" required value={fullName} onChange={e => setFullName(e.target.value)} placeholder="John Doe" />
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Age <span className="optional">(optional)</span></label>
                  <input type="number" value={age} onChange={e => setAge(e.target.value)} placeholder="16" />
                </div>
                <div className="field">
                  <label>Country <span className="optional">(optional)</span></label>
                  <input type="text" value={country} onChange={e => setCountry(e.target.value)} placeholder="Nigeria" />
                </div>
              </div>
              <div className="field">
                <label>Class ID</label>
                <input type="text" value={classId} onChange={e => setClassId(e.target.value)} placeholder="e.g. SSS 1" />
              </div>
              <div className="field">
                <label>Subjects <span className="optional">(comma separated)</span></label>
                <input type="text" value={subjects} onChange={e => setSubjects(e.target.value)} placeholder="Biology, Math, Physics" />
              </div>
            </>
          )}

          {error && <div className="field-error">{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Please wait...' : (mode === 'login' ? 'Sign In' : 'Create Account')}
          </button>
        </form>
      </div>
    </div>
  );
};
