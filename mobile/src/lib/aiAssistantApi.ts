import { supabase } from '@/lib/supabase';
import type { McpStatus } from '@/lib/aiAssistant';

/**
 * The member functions the app calls (mcp_foundation_2026_11_21.sql and
 * mcp_multi_assistant_2026_11_22.sql). Each needs a signed-in session; anon
 * is refused with 42501.
 */
export async function fetchMcpStatus(): Promise<McpStatus> {
  const { data, error } = await supabase.rpc('mcp_my_status');
  if (error) throw error;
  return data as McpStatus;
}

/** Ends every connected assistant's access. The rows are kept, with revoked_at. */
export async function disconnectMcp(): Promise<void> {
  const { error } = await supabase.rpc('mcp_disconnect');
  if (error) throw error;
}

/**
 * Ends ONE assistant's access (mcp_multi_assistant_2026_11_22.sql). `null`
 * comes from a server older than that, which only knows Disconnect-all.
 */
export async function disconnectMcpAssistant(assistant: string | null): Promise<void> {
  if (assistant === null) return disconnectMcp();
  const { error } = await supabase.rpc('mcp_disconnect_assistant', { p_assistant: assistant });
  if (error) throw error;
}
