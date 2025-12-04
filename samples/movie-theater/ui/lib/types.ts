export interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
  agent?: string;
  timestamp: Date;
}

export interface Agent {
  name: string;
  description: string;
  handoffs: string[];
  tools: string[];
  /** List of input guardrail identifiers for this agent */
  input_guardrails: string[];
}

export type EventType =
  | "message"
  | "handoff"
  | "tool_call"
  | "tool_output"
  | "context_update";

export interface AgentEvent {
  id: string;
  type: EventType;
  agent: string;
  content: string;
  timestamp: Date;
  metadata?: {
    source_agent?: string;
    target_agent?: string;
    tool_name?: string;
    tool_args?: Record<string, any>;
    tool_result?: any;
    context_key?: string;
    context_value?: any;
    changes?: Record<string, any>;
  };
}

export interface GuardrailCheck {
  id: string;
  name: string;
  input: string;
  reasoning: string;
  passed: boolean;
  timestamp: Date;
}

// Cinema specific context type
export interface CinemaContext {
  customer_name?: string;
  confirmation_number?: string;
  seats?: string[];
  movie_title?: string;
  cinema_name?: string;
  city?: string;
  session_datetime?: string;
  room_number?: string;
  ticket_count?: number;
  ticket_type?: string;
  account_number?: string;
}
