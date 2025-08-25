import logging
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

class LLMLogger:
    """Logger especializado para capturar interações com LLMs e transições de agentes."""
    
    def __init__(self, log_file: str = "llm.log"):
        self.log_file = Path(log_file)
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Configura o logger com formatação específica para LLM."""
        logger = logging.getLogger("llm_logger")
        logger.setLevel(logging.INFO)
        
        # Evita duplicação de handlers
        if logger.handlers:
            return logger
        
        # Handler para arquivo
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Formato personalizado para logs de LLM
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        return logger
    
    def log_llm_request(self, 
                       agent_name: str, 
                       model: str, 
                       input_data: Any, 
                       conversation_id: Optional[str] = None,
                       context: Optional[Dict] = None) -> None:
        """Log de entrada para LLM."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "llm_request",
            "agent": agent_name,
            "model": model,
            "conversation_id": conversation_id,
            "input": self._sanitize_input(input_data),
            "context": context
        }
        self.logger.info(f"LLM REQUEST: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_llm_response(self, 
                        agent_name: str, 
                        model: str, 
                        response: Any, 
                        conversation_id: Optional[str] = None,
                        metadata: Optional[Dict] = None) -> None:
        """Log de saída da LLM."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "llm_response",
            "agent": agent_name,
            "model": model,
            "conversation_id": conversation_id,
            "response": self._sanitize_response(response),
            "metadata": metadata
        }
        self.logger.info(f"LLM RESPONSE: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_agent_transition(self, 
                           from_agent: str, 
                           to_agent: str, 
                           reason: Optional[str] = None,
                           conversation_id: Optional[str] = None,
                           context: Optional[Dict] = None) -> None:
        """Log de transição entre agentes."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "agent_transition",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "conversation_id": conversation_id,
            "reason": reason,
            "context": context
        }
        self.logger.info(f"AGENT TRANSITION: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_tool_call(self, 
                     agent_name: str, 
                     tool_name: str, 
                     tool_args: Any,
                     conversation_id: Optional[str] = None) -> None:
        """Log de chamada de ferramenta."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "tool_call",
            "agent": agent_name,
            "tool": tool_name,
            "conversation_id": conversation_id,
            "arguments": self._sanitize_input(tool_args)
        }
        self.logger.info(f"TOOL CALL: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_tool_result(self, 
                       agent_name: str, 
                       tool_name: str, 
                       result: Any,
                       conversation_id: Optional[str] = None) -> None:
        """Log de resultado de ferramenta."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "tool_result",
            "agent": agent_name,
            "tool": tool_name,
            "conversation_id": conversation_id,
            "result": self._sanitize_response(result)
        }
        self.logger.info(f"TOOL RESULT: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_guardrail_check(self, 
                           agent_name: str, 
                           guardrail_name: str, 
                           input_text: str,
                           passed: bool,
                           reasoning: Optional[str] = None,
                           conversation_id: Optional[str] = None) -> None:
        """Log de verificação de guardrail."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "guardrail_check",
            "agent": agent_name,
            "guardrail": guardrail_name,
            "conversation_id": conversation_id,
            "input": input_text,
            "passed": passed,
            "reasoning": reasoning
        }
        self.logger.info(f"GUARDRAIL CHECK: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_error(self, 
                 agent_name: str, 
                 error_type: str, 
                 error_message: str,
                 conversation_id: Optional[str] = None,
                 context: Optional[Dict] = None) -> None:
        """Log de erros."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "error",
            "agent": agent_name,
            "error_type": error_type,
            "conversation_id": conversation_id,
            "message": error_message,
            "context": context
        }
        self.logger.error(f"ERROR: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_conversation_start(self, 
                             conversation_id: str, 
                             initial_agent: str,
                             context: Optional[Dict] = None) -> None:
        """Log de início de conversa."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "conversation_start",
            "conversation_id": conversation_id,
            "initial_agent": initial_agent,
            "context": context
        }
        self.logger.info(f"CONVERSATION START: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def log_conversation_end(self, 
                           conversation_id: str, 
                           final_agent: str,
                           duration_seconds: Optional[float] = None) -> None:
        """Log de fim de conversa."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "conversation_end",
            "conversation_id": conversation_id,
            "final_agent": final_agent,
            "duration_seconds": duration_seconds
        }
        self.logger.info(f"CONVERSATION END: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def _sanitize_input(self, data: Any) -> Any:
        """Sanitiza dados de entrada para logging seguro."""
        if isinstance(data, str):
            # Limita o tamanho de strings muito longas
            return data[:1000] + "..." if len(data) > 1000 else data
        elif isinstance(data, list):
            return [self._sanitize_input(item) for item in data[:10]]  # Limita a 10 itens
        elif isinstance(data, dict):
            return {k: self._sanitize_input(v) for k, v in list(data.items())[:20]}  # Limita a 20 chaves
        return str(data)[:500] if len(str(data)) > 500 else data
    
    def _sanitize_response(self, data: Any) -> Any:
        """Sanitiza dados de resposta para logging seguro."""
        return self._sanitize_input(data)

# Instância global do logger
llm_logger = LLMLogger() 