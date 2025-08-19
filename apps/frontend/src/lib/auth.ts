function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : null;
}

export async function login(username: string, password: string): Promise<boolean> {
  try {
    const csrf = getCookie('csrftoken');
    const res = await fetch('/api/auth/login/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRFToken': csrf } : {})
      },
      body: JSON.stringify({ username, password }),
      credentials: 'include'
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function signOut(): Promise<boolean> {
  try {
    const csrf = getCookie('csrftoken');
    const res = await fetch('/api/auth/logout/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRFToken': csrf } : {})
      },
      credentials: 'include'
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function registerUser(
  username: string,
  password: string,
  password_retype: string
): Promise<boolean> {
  try {
    const csrf = getCookie('csrftoken');
    const res = await fetch('/api/users/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRFToken': csrf } : {})
      },
      body: JSON.stringify({ username, password, password_retype }),
      credentials: 'include'
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function getCurrentUser(): Promise<{
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  is_staff: boolean;
} | null> {
  try {
    const res = await fetch('/api/users/me/', {
      method: 'GET',
      credentials: 'include'
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}


