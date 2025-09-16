'use client';

import { useEffect, useState } from 'react';

type AuthUser = {
  id?: number;
  username?: string | null;
  fullName?: string | null;
  email?: string | null;
  imageUrl?: string;
  role?: string | null;
} | null;

export function useAuth() {
  const [user, setUser] = useState<AuthUser>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await fetch('/api/users/me/', { credentials: 'include' });
        if (!active) return;
        if (res.ok) {
          const u = await res.json();
          setUser({
            id: u.id,
            username: u.username,
            fullName: `${u.first_name || ''} ${u.last_name || ''}`.trim() || u.username,
            email: u.email || null,
            imageUrl: undefined,
            role: u.role || null
          });
        } else {
          setUser(null);
        }
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  return { user, loading };
}



