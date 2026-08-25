export interface SchemaField {
  name: string;
  title: string;
  type: string;
  description: string;
}

export interface SchemaTable {
  name: string;
  title: string;
  description: string;
  fields: SchemaField[];
}

export interface ThinkingStep {
  id: string;
  type: 'thinking' | 'tool_call' | 'tool_result';
  label: string;
  detail?: string;
  timestamp: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: number;
  loading?: boolean;
  steps: ThinkingStep[];
}


export interface HealthResponse {
  ok: boolean;
  service: string;
  version: string;
}

export interface SessionMetadata {
  tables: string[];
  summary?: string | null;
}

export interface Session {
  id: string;
  title: string;
  messages: ChatMessage[];
  status?: 'thinking' | 'done' | 'error';
  metadata?: SessionMetadata;
  created_at?: string;
 updated_at?: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  status?: 'thinking' | 'done' | 'error';
  updated_at: string;
  created_at: string;
  message_count: number;
  unread?: boolean;
  // true while the session exists only as a client-side optimistic placeholder
  // (no first message sent yet, backend doesn't know about it)
  local?: boolean;
}

export type MemoryCategory = 'preference' | 'correction' | 'context' | string;

export interface Memory {
  id: string;
  key: string;
  content: string;
  category: MemoryCategory;
  updated_at: string;
}

export interface DatasetColumn {
  name: string;
  type: string;
  title: string;
  sample_values: string;
  null_count: number;
  unique_count: number;
}

export interface Dataset {
  name: string;
  filename: string;
  file_type: string;
  row_count: number;
  columns: DatasetColumn[];
}
