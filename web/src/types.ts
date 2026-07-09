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
  routedTo?: string;
  timestamp: number;
  loading?: boolean;
  steps: ThinkingStep[];
}

export interface ChatResponse {
  answer: string;
  routed_to: string;
  question: string;
}

export interface HealthResponse {
  ok: boolean;
  service: string;
  version: string;
}

export interface Session {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}
