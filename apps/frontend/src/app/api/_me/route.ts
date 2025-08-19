import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.API_URL || 'http://api:8000';

export async function GET(req: NextRequest) {
  try {
    const cookie = req.headers.get('cookie') || '';
    const res = await fetch(`${API_URL}/api/users/me/`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json', cookie }
    });
    if (!res.ok) {
      return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ detail: 'Server error' }, { status: 500 });
  }
}


