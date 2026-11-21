import { supabase } from '@/lib/supabase';
import type { McpStatus } from '@/lib/aiAssistant';

/**
 * The two member functions the app calls (mcp_foundation_2026_11_21.sql).
 * Both need a signed-in session; anon is refused with 42501.
 */
export async function fetchMcpStatus(): Promise<McpStatus> {
  const { data, error } = await supabase.rpc('mcp_my_status');
  if (error) throw error;
  return data as McpStatus;
}

/** Ends the connected app's access. The row is kept, with revoked_at. */
export async function disconnectMcp(): Promise<void> {
  const { error } = await supabase.rpc('mcp_disconnect');
  if (error) throw error;
}
