export interface Message {
  id: string
  content: string
  role: "user" | "assistant"
  agent?: string
  timestamp: Date
}

export interface Agent {
  name: string
  description: string
  handoffs: string[]
  tools: string[]
  /** List of input guardrail identifiers for this agent */
  input_guardrails: string[]
}

export type EventType = "message" | "handoff" | "tool_call" | "tool_output" | "context_update"

export interface AgentEvent {
  id: string
  type: EventType
  agent: string
  content: string
  timestamp: Date
  metadata?: {
    source_agent?: string
    target_agent?: string
    tool_name?: string
    tool_args?: Record<string, any>
    tool_result?: any
    context_key?: string
    context_value?: any
    changes?: Record<string, any>
  }
}

export interface GuardrailCheck {
  id: string
  name: string
  input: string
  reasoning: string
  passed: boolean
  timestamp: Date
}

// Agents config types for UI editor
export interface AgentConfig {
  name: string
  description: string
  model: string
  instructions: { mode: "builtin"; builtin: string } | { mode: "custom"; value: string }
  tools: string[]
  input_guardrails: string[]
  handoffs: { target: string; on_handoff?: string }[]
}

export interface RegistryConfig {
  primary_agent_name: string
  agents: AgentConfig[]
}

