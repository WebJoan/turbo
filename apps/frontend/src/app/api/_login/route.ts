import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.API_URL || 'http://api:8000';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${API_URL}/api/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    // Pass through Set-Cookie headers to browser
    const headers = new Headers();
    const setCookie = (res.headers as any).getSetCookie?.() || [];
    for (const c of setCookie) headers.append('Set-Cookie', c);

    if (!res.ok) {
      return new NextResponse(await res.text(), { status: res.status, headers });
    }
    return new NextResponse(await res.text(), { status: res.status, headers });
  } catch (e) {
    return NextResponse.json({ detail: 'Server error' }, { status: 500 });
  }
}


