```mermaid
graph TD
    subgraph Frontend (Next.js UI)
        UI_Page["User Interface (page.tsx)"]
        UI_Chat["Chat Component (Chat.tsx)"]
        UI_AgentPanel["Agent Panel (agent-panel.tsx)"]
        UI_API["UI API Lib (api.ts)"]
    end

    subgraph Backend (Python FastAPI)
        B_API["FastAPI App (api.py)"]
        B_ChatEndpoint["/chat Endpoint"]
        B_ConversationStore["InMemoryConversationStore"]
        B_AgentRunner["Agent Execution Logic (run_gemini_agent or Runner.run)"]
        B_Main["Agent Definitions (main.py)"]
        B_ModelConfig["Model Provider Logic (MODEL_PROVIDER, get_model_config)"]

        subgraph Agents
            A_Triage["Triage Agent"]
            A_Seat["Seat Booking Agent"]
            A_FlightStatus["Flight Status Agent"]
            A_FAQ["FAQ Agent"]
            A_Cancel["Cancellation Agent"]
            A_GuardrailRelevance["Relevance Guardrail Agent"]
            A_GuardrailJailbreak["Jailbreak Guardrail Agent"]
        end

        B_Tools["Tools (faq_lookup_tool, update_seat, etc.)"]
    end

    subgraph AI Models
        M_OpenAI["OpenAI Models (GPT-3.5/4)"]
        M_Gemini["Google Gemini Models (Flash/Pro)"]
    end

    %% UI Interactions
    UI_Page --> UI_Chat
    UI_Page --> UI_AgentPanel
    UI_Chat -- "Sends message" --> UI_API
    UI_API -- "POST /chat" --> B_ChatEndpoint

    %% Backend Core Logic
    B_ChatEndpoint -- "Uses" --> B_ConversationStore
    B_ChatEndpoint -- "Gets agent, calls runner" --> B_AgentRunner
    B_AgentRunner -- "Selects based on MODEL_PROVIDER" --> M_OpenAI
    B_AgentRunner -- "Selects based on MODEL_PROVIDER" --> M_Gemini
    B_AgentRunner -- "Executes" --> A_Triage
    B_AgentRunner -- "Executes" --> A_Seat
    B_AgentRunner -- "Executes" --> A_FlightStatus
    B_AgentRunner -- "Executes" --> A_FAQ
    B_AgentRunner -- "Executes" --> A_Cancel

    B_Main -- "Defines agents with specific models" --> B_ModelConfig
    B_ModelConfig -- "Provides model name (OpenAI or Gemini)" --> Agents

    %% Agent Interactions
    A_Triage -- "Handoff" --> A_Seat
    A_Triage -- "Handoff" --> A_FlightStatus
    A_Triage -- "Handoff" --> A_FAQ
    A_Triage -- "Handoff" --> A_Cancel
    A_Seat -- "Uses" --> B_Tools
    A_FlightStatus -- "Uses" --> B_Tools
    A_FAQ -- "Uses" --> B_Tools
    A_Cancel -- "Uses" --> B_Tools

    Agents -- "Input processed by" --> A_GuardrailRelevance
    Agents -- "Input processed by" --> A_GuardrailJailbreak
    A_GuardrailRelevance -- "Uses specific AI model" --> B_ModelConfig
    A_GuardrailJailbreak -- "Uses specific AI model" --> B_ModelConfig

    %% Agent to Model (General Path)
    A_Triage -- "LLM Call via Runner" --> B_AgentRunner
    A_Seat -- "LLM Call via Runner" --> B_AgentRunner
    A_FlightStatus -- "LLM Call via Runner" --> B_AgentRunner
    A_FAQ -- "LLM Call via Runner" --> B_AgentRunner
    A_Cancel -- "LLM Call via Runner" --> B_AgentRunner
    A_GuardrailRelevance -- "LLM Call via Runner" --> B_AgentRunner
    A_GuardrailJailbreak -- "LLM Call via Runner" --> B_AgentRunner

    %% Styling
    classDef frontend fill:#D6EAF8,stroke:#2E86C1,stroke-width:2px;
    classDef backend fill:#D5F5E3,stroke:#28B463,stroke-width:2px;
    classDef models fill:#FDEDEC,stroke:#E74C3C,stroke-width:2px;
    classDef agentsBackend fill:#E8DAEF,stroke:#8E44AD,stroke-width:2px;

    class UI_Page,UI_Chat,UI_AgentPanel,UI_API frontend;
    class B_API,B_ChatEndpoint,B_ConversationStore,B_AgentRunner,B_Main,B_ModelConfig,B_Tools backend;
    class A_Triage,A_Seat,A_FlightStatus,A_FAQ,A_Cancel,A_GuardrailRelevance,A_GuardrailJailbreak agentsBackend;
    class M_OpenAI,M_Gemini models;
```

**Diagram Explanation:**

*   **Frontend (Next.js UI):** Handles user interaction, displays chat, and shows agent activity. It communicates with the backend via an API library.
*   **Backend (Python FastAPI):**
    *   Receives requests at the `/chat` endpoint.
    *   Manages conversation state using `InMemoryConversationStore`.
    *   `Model Provider Logic` determines whether to use OpenAI or Gemini based on the `MODEL_PROVIDER` environment variable.
    *   `Agent Definitions (main.py)` now use `get_model_config` to assign either an OpenAI model string or a Gemini model string to each agent (including guardrail agents).
    *   `Agent Execution Logic` is the core part that runs the agent. This is now conditional:
        *   If the agent is configured for Gemini (model name starts with "gemini-"), it uses the new `run_gemini_agent` function (which directly calls the Gemini API).
        *   Otherwise (for OpenAI models), it uses the existing `Runner.run` from the `openai-agents` SDK.
    *   `Agents` (Triage, Seat Booking, etc., including Guardrail Agents) are defined with specific instructions and tools. Their underlying LLM calls are routed through the `Agent Execution Logic`.
    *   `Tools` are functions that agents can call (e.g., `faq_lookup_tool`).
*   **AI Models:** Represents the swappable LLM providers: OpenAI and Google Gemini. The `Agent Execution Logic` in the backend selects which model service to call.

**Key Changes for Gemini Integration:**

1.  **Dual Model Capability:** The system can now theoretically use either OpenAI or Gemini models, configured via an environment variable.
2.  **Conditional Execution Path:** The backend has a new execution path (`run_gemini_agent`) for Gemini models, bypassing the `openai-agents` SDK's default runner for these specific agents. OpenAI models continue to use the SDK's runner.
3.  **Model Configuration:** Agent definitions are now passed Gemini-specific model names (e.g., "gemini-1.5-flash-latest") if Gemini is selected as the provider.
4.  **Guardrail Agents & Model Selection:** Guardrail agents (Relevance, Jailbreak) are also configured via `get_model_config`. However, their execution relies on the `openai-agents` SDK's internal `Runner.run`. If this runner is strictly OpenAI-based, Gemini guardrail agents might not function correctly without SDK modification. The diagram shows them using the common `B_ModelConfig` and `B_AgentRunner` path, but this highlights a potential area of friction.

This diagram illustrates the intended architecture with the Gemini integration. The dashed lines or areas needing careful testing would be the full functionality of tools and handoffs within `run_gemini_agent`, and the behavior of guardrail agents when `MODEL_PROVIDER` is set to "gemini".
