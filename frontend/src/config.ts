// Centralized configuration — single source of truth for all frontend modules.
// In production, VITE_API_BASE is set via .env or build-time variables.

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
export const ALLOW_LEGACY_AUTH = (import.meta.env.VITE_ALLOW_LEGACY_AUTH || 'false').toLowerCase() === 'true';

// Default user IDs — used for initial token acquisition.
export const STUDENT_USER_ID = 'sovereign_user_1';
export const ADMIN_USER_ID = 'sovereign_admin_1';

export async function getAuthToken(userId: string): Promise<string> {
    const token = localStorage.getItem(`jwt_${userId}`);
    if (!token) {
        throw new Error('Missing auth token. Please login again.');
    }
    return token;
}

export async function authHeaders(userId: string, _role: string = 'student'): Promise<Record<string, string>> {
    try {
        const token = await getAuthToken(userId);
        return {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        };
    } catch {
        if (ALLOW_LEGACY_AUTH) {
            return {
                'X-User-ID': userId,
                'Content-Type': 'application/json',
            };
        }
        throw new Error('Authentication required.');
    }
}

export async function authHeadersMultipart(userId: string, _role: string = 'student'): Promise<Record<string, string>> {
    try {
        const token = await getAuthToken(userId);
        return { 'Authorization': `Bearer ${token}` };
    } catch {
        if (ALLOW_LEGACY_AUTH) {
            return { 'X-User-ID': userId };
        }
        throw new Error('Authentication required.');
    }
}

export function clearAuthToken(): void {
    const currentUser = localStorage.getItem('current_user');
    if (currentUser) {
        localStorage.removeItem(`jwt_${currentUser}`);
    }
}

/** Checks API responses for auth failures (expired JWT) and force-redirects to login. */
export function checkAuthExpiry(res: Response): void {
    if (res.status === 401) {
        const currentUser = localStorage.getItem('current_user');
        if (currentUser) localStorage.removeItem(`jwt_${currentUser}`);
        localStorage.removeItem('current_user');
        localStorage.removeItem('current_role');
        window.location.reload();
    }
}
