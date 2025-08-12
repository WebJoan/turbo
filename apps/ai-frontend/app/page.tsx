import { MyAssistant } from "@/components/MyAssistant";
import { AuthGuard } from "@/components/AuthGuard";
import { Navigation } from "@/components/Navigation";

export const dynamic = 'force-dynamic';

export default function Home() {
  return (
    <AuthGuard>
      <Navigation />
      <main className="min-h-screen">
        <MyAssistant />
      </main>
    </AuthGuard>
  );
}
