#!/usr/bin/env python3
"""
Script de teste para verificar o sistema de logging
"""

import asyncio
import json
from llm_logger import llm_logger

async def test_logging():
    """Testa todas as funcionalidades de logging"""
    
    print("🧪 Testando sistema de logging...")
    
    # Teste de início de conversa
    llm_logger.log_conversation_start(
        conversation_id="test-123",
        initial_agent="Triage Agent",
        context={"test": "data"}
    )
    
    # Teste de requisição LLM
    llm_logger.log_llm_request(
        agent_name="Triage Agent",
        model="gpt-4.1",
        input_data="Olá, preciso de ajuda com meu voo",
        conversation_id="test-123",
        context={"passenger_name": "João Silva"}
    )
    
    # Teste de resposta LLM
    llm_logger.log_llm_response(
        agent_name="Triage Agent",
        model="gpt-4.1",
        response="Como posso ajudá-lo com seu voo?",
        conversation_id="test-123",
        metadata={"tokens_used": 150}
    )
    
    # Teste de transição de agente
    llm_logger.log_agent_transition(
        from_agent="Triage Agent",
        to_agent="Seat Booking Agent",
        reason="user_requested_seat_change",
        conversation_id="test-123",
        context={"confirmation_number": "ABC123"}
    )
    
    # Teste de chamada de ferramenta
    llm_logger.log_tool_call(
        agent_name="Seat Booking Agent",
        tool_name="update_seat",
        tool_args={"confirmation_number": "ABC123", "new_seat": "12A"},
        conversation_id="test-123"
    )
    
    # Teste de resultado de ferramenta
    llm_logger.log_tool_result(
        agent_name="Seat Booking Agent",
        tool_name="update_seat",
        result="Assento atualizado com sucesso para 12A",
        conversation_id="test-123"
    )
    
    # Teste de guardrail
    llm_logger.log_guardrail_check(
        agent_name="Triage Agent",
        guardrail_name="Relevance Guardrail",
        input_text="Olá, preciso de ajuda com meu voo",
        passed=True,
        reasoning="Mensagem relevante para serviço de companhia aérea",
        conversation_id="test-123"
    )
    
    # Teste de erro
    llm_logger.log_error(
        agent_name="Triage Agent",
        error_type="guardrail_tripwire",
        error_message="Guardrail de relevância acionado",
        conversation_id="test-123",
        context={"input": "Mensagem irrelevante"}
    )
    
    # Teste de fim de conversa
    llm_logger.log_conversation_end(
        conversation_id="test-123",
        final_agent="Seat Booking Agent",
        duration_seconds=45.5
    )
    
    print("✅ Testes de logging concluídos!")
    print("📝 Verifique o arquivo llm.log para ver os resultados")

if __name__ == "__main__":
    asyncio.run(test_logging()) 