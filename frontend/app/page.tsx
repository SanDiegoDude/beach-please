import { listBeaches } from "@/lib/api";
import type { Beach } from "@/lib/types";
import { ChatPage } from "@/components/ChatPage";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let beaches: Beach[] = [];
  try {
    beaches = await listBeaches();
  } catch {
    beaches = [];
  }

  return <ChatPage featured={beaches} />;
}
