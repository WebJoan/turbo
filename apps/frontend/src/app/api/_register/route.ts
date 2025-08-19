import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.API_URL || 'http://api:8000';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${API_URL}/api/users/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      credentials: 'include'
    });
    if (!res.ok) {
      return new NextResponse(await res.text(), { status: res.status });
    }
    return new NextResponse(await res.text(), { status: res.status });
  } catch (e) {
    return NextResponse.json({ detail: 'Server error' }, { status: 500 });
  }
}



