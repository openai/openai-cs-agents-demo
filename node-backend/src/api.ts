import express, { Request, Response } from 'express';
import cors from 'cors';
import { v4 as uuidv4 } from 'uuid';
import { run } from '@openai/agents';
import {
  triageAgent,
  faqAgent,
  seatBookingAgent,
  flightStatusAgent,
  cancellationAgent,
  createInitialContext,
  AirlineAgentContext,
} from './main';

// =========================
// Types
// =========================

interface ChatRequest {
  conversation_id?: string;
  message: string;
}

interface MessageResponse {
  content: string;
  agent: string;
}

interface AgentEvent {
  id: string;
  type: string;
  agent: string;
  content: string;
  metadata?: Record<string, any>;
  timestamp?: number;
}

interface GuardrailCheck {
  id: string;
  name: string;
  input: string;
  reasoning: string;
  passed: boolean;
  timestamp: number;
}

interface ChatResponse {
  conversation_id: string;
  current_agent: string;
  messages: MessageResponse[];
  events: AgentEvent[];
  context: Record<string, any>;
  agents: Record<string, any>[];
  guardrails: GuardrailCheck[];
}

interface ConversationState {
  input_items: any[];
  context: AirlineAgentContext;
  current_agent: string;
}

// =========================
// In-memory store for conversation state
// =========================

abstract class ConversationStore {
  abstract get(conversationId: string): ConversationState | undefined;
  abstract save(conversationId: string, state: ConversationState): void;
}

class InMemoryConversationStore extends ConversationStore {
  private static conversations: Map<string, ConversationState> = new Map();

  get(conversationId: string): ConversationState | undefined {
    return InMemoryConversationStore.conversations.get(conversationId);
  }

  save(conversationId: string, state: ConversationState): void {
    InMemoryConversationStore.conversations.set(conversationId, state);
  }
}

// TODO: when deploying this app in scale, switch to your own production-ready implementation
const conversationStore = new InMemoryConversationStore();

// =========================
// Helpers
// =========================

function getAgentByName(name: string) {
  const agents: Record<string, any> = {
    [triageAgent.name]: triageAgent,
    [faqAgent.name]: faqAgent,
    [seatBookingAgent.name]: seatBookingAgent,
    [flightStatusAgent.name]: flightStatusAgent,
    [cancellationAgent.name]: cancellationAgent,
  };
  return agents[name] || triageAgent;
}

function getGuardrailName(g: any): string {
  // Extract a friendly guardrail name - simplified for TypeScript
  if (g && g.name && typeof g.name === 'string') {
    return g.name;
  }
  return 'Unknown Guardrail';
}

function buildAgentsList(): Record<string, any>[] {
  const makeAgentDict = (agent: any) => ({
    name: agent.name,
    description: agent.handoffDescription || '',
    handoffs: (agent.handoffs || []).map((h: any) => h.name || ''),
    tools: (agent.tools || []).map((t: any) => t.name || ''),
    inputGuardrails: (agent.inputGuardrails || []).map((g: any) => getGuardrailName(g)),
  });

  return [
    makeAgentDict(triageAgent),
    makeAgentDict(faqAgent),
    makeAgentDict(seatBookingAgent),
    makeAgentDict(flightStatusAgent),
    makeAgentDict(cancellationAgent),
  ];
}

// =========================
// Express App Setup
// =========================

const app = express();

// Middleware
app.use(cors({
  origin: 'http://localhost:3000',
  credentials: true,
}));
app.use(express.json());

// =========================
// Main Chat Endpoint
// =========================

app.post('/chat', async (req: Request, res: Response) => {
  try {
    const { conversation_id, message }: ChatRequest = req.body;

    // Initialize or retrieve conversation state
    const isNew = !conversation_id || !conversationStore.get(conversation_id);
    let conversationId: string;
    let state: ConversationState;

    if (isNew) {
      conversationId = uuidv4().replace(/-/g, '');
      const ctx = createInitialContext();
      const currentAgentName = triageAgent.name;
      
      state = {
        input_items: [],
        context: ctx,
        current_agent: currentAgentName,
      };

      // If empty message, just return initial state
      if (!message.trim()) {
        conversationStore.save(conversationId, state);
        const response: ChatResponse = {
          conversation_id: conversationId,
          current_agent: currentAgentName,
          messages: [],
          events: [],
          context: { ...ctx },
          agents: buildAgentsList(),
          guardrails: [],
        };
        res.json(response);
        return;
      }
    } else {
      conversationId = conversation_id!;
      state = conversationStore.get(conversationId)!;
    }

    let currentAgent = getAgentByName(state.current_agent);
    state.input_items.push({ content: message, role: 'user' });
    const oldContext = { ...state.context };
    let guardrailChecks: GuardrailCheck[] = [];

    try {
      // Run the agent with conversation history - pass the full input_items array
      const result = await run(currentAgent, state.input_items, { 
        context: state.context
      });
      
      const messages: MessageResponse[] = [];
      const events: AgentEvent[] = [];

      // Process the final output
      if (result.finalOutput) {
        const content = typeof result.finalOutput === 'string' ? result.finalOutput : JSON.stringify(result.finalOutput);
        
        messages.push({ content, agent: currentAgent.name });
        events.push({
          id: uuidv4().replace(/-/g, ''),
          type: 'message',
          agent: currentAgent.name,
          content,
        });

        // Handle special seat map display
        if (content === 'DISPLAY_SEAT_MAP') {
          messages.push({
            content: 'DISPLAY_SEAT_MAP',
            agent: currentAgent.name,
          });
        }
      }

      // Check for context changes
      const newContext = { ...state.context };
      const changes: Record<string, any> = {};
      
      for (const key in newContext) {
        if (oldContext[key as keyof AirlineAgentContext] !== newContext[key as keyof AirlineAgentContext]) {
          changes[key] = newContext[key as keyof AirlineAgentContext];
        }
      }

      if (Object.keys(changes).length > 0) {
        events.push({
          id: uuidv4().replace(/-/g, ''),
          type: 'context_update',
          agent: currentAgent.name,
          content: '',
          metadata: { changes },
        });
      }

      // Update conversation history using the result.history from the SDK
      if (result.history) {
        state.input_items = result.history;
      } else if (result.finalOutput) {
        // Fallback: manually add assistant response if history not available
        state.input_items.push({ 
          role: 'assistant', 
          content: typeof result.finalOutput === 'string' ? result.finalOutput : JSON.stringify(result.finalOutput)
        });
      }
      
      state.current_agent = currentAgent.name;
      conversationStore.save(conversationId, state);

      // Build guardrail results: mark any as passed for successful runs
      const finalGuardrails: GuardrailCheck[] = [];
      if (currentAgent.inputGuardrails) {
        for (const g of currentAgent.inputGuardrails) {
          const name = getGuardrailName(g);
          const failed = guardrailChecks.find(gc => gc.name === name);
          if (failed) {
            finalGuardrails.push(failed);
          } else {
            finalGuardrails.push({
              id: uuidv4().replace(/-/g, ''),
              name,
              input: message,
              reasoning: '',
              passed: true,
              timestamp: Date.now(),
            });
          }
        }
      }

      const response: ChatResponse = {
        conversation_id: conversationId,
        current_agent: currentAgent.name,
        messages,
        events,
        context: state.context,
        agents: buildAgentsList(),
        guardrails: finalGuardrails,
      };

      res.json(response);

    } catch (error: any) {
      console.error('Error running agent:', error);
      
      // Handle guardrail or other errors
      if (error.name === 'InputGuardrailTripwireTriggered' || error.message?.includes('guardrail')) {
        // Extract guardrail info if available
        const grReasoning = error.reason || error.message || '';
        const grTimestamp = Date.now();
        
        if (currentAgent.inputGuardrails) {
          for (const g of currentAgent.inputGuardrails) {
            guardrailChecks.push({
              id: uuidv4().replace(/-/g, ''),
              name: getGuardrailName(g),
              input: message,
              reasoning: grReasoning,
              passed: false,
              timestamp: grTimestamp,
            });
          }
        }
      }

      const refusal = "Sorry, I can only answer questions related to airline travel.";
      state.input_items.push({ role: 'assistant', content: refusal });
      
      const response: ChatResponse = {
        conversation_id: conversationId,
        current_agent: currentAgent.name,
        messages: [{ content: refusal, agent: currentAgent.name }],
        events: [],
        context: state.context,
        agents: buildAgentsList(),
        guardrails: guardrailChecks,
      };

      res.json(response);
    }

  } catch (error) {
    console.error('API Error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// =========================
// Health Check
// =========================

app.get('/health', (req: Request, res: Response) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// =========================
// Start Server
// =========================

const PORT = process.env.PORT || 8000;

app.listen(PORT, () => {
  console.log(`🚀 Servidor rodando na porta ${PORT}`);
  console.log(`📡 API disponível em http://localhost:${PORT}`);
});

export default app;
