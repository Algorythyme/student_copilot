// Centralized configuration — single source of truth for all frontend modules.
// In production, VITE_API_BASE is set via .env or build-time variables.

import { getSupabaseAccessToken, isSupabaseConfigured, signOutSupabase } from './supabase';

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export async function getAuthToken(userId: string): Promise<string> {
    if (isSupabaseConfigured()) {
        const token = await getSupabaseAccessToken();
        if (token) {
            return token;
        }
        throw new Error('Supabase session expired. Please sign in again.');
    }

    const token = localStorage.getItem(`jwt_${userId}`);
    if (!token) {
        throw new Error('Missing auth token. Please login again.');
    }
    return token;
}

export async function authHeaders(userId: string): Promise<Record<string, string>> {
    const token = await getAuthToken(userId);
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    };
}

export async function authHeadersMultipart(userId: string): Promise<Record<string, string>> {
    const token = await getAuthToken(userId);
    return { 'Authorization': `Bearer ${token}` };
}

export async function clearAuthToken(): Promise<void> {
    if (isSupabaseConfigured()) {
        await signOutSupabase();
    }
    const currentUser = localStorage.getItem('current_user');
    if (currentUser) {
        localStorage.removeItem(`jwt_${currentUser}`);
    }
}

/** Checks API responses for auth failures (expired JWT) and force-redirects to login. */
export function checkAuthExpiry(res: Response): void {
    if (res.status === 401) {
        void clearAuthToken();
        localStorage.removeItem('current_user');
        window.location.reload();
    }
}
