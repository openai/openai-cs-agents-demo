import { run } from '@openai/agents';
import { triageAgent, createInitialContext } from './main';

async function main() {
  try {
    // Cria contexto inicial
    const context = createInitialContext();
    console.log('Contexto inicial:', context);

    // Exemplo de conversa com o agente de triagem
    const result = await run(
      triageAgent, 
      'Olá, gostaria de verificar o status do meu voo FLT-123'
    );

    console.log('Resposta do agente:', result.finalOutput);
  } catch (error) {
    console.error('Erro ao executar o agente:', error);
  }
}

// Executa apenas se este arquivo for executado diretamente
if (require.main === module) {
  main().catch(console.error);
}

export { main }; 