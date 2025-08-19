import { NextResponse } from 'next/server';

const API_URL = process.env.API_URL || 'http://api:8000';

export async function POST() {
  try {
    const res = await fetch(`${API_URL}/api/auth/logout/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include'
    });
    const headers = new Headers();
    const setCookie = res.headers.getSetCookie?.() || [];
    for (const c of setCookie) headers.append('Set-Cookie', c);
    return new NextResponse(await res.text(), { status: res.status, headers });
  } catch (e) {
    return NextResponse.json({ detail: 'Server error' }, { status: 500 });
  }
}



