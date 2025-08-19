import { NextRequest, NextResponse } from 'next/server';

const protectedMatchers = [/^\/dashboard(\/.*)?$/];

export function middleware(req: NextRequest) {
  const url = req.nextUrl.clone();
  const isProtected = protectedMatchers.some((re) => re.test(url.pathname));
  const accessToken = req.cookies.get('access_token')?.value;

  if (isProtected && !accessToken) {
    url.pathname = '/auth/sign-in';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)'
  ]
};
