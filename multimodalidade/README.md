# Entrega multimodal: texto e áudio

## Modalidades suportadas

- **Texto:** pergunta digitada é enviada a `POST /api/orientar`; o assistente
  consulta o grafo multiagente e a base RAG e retorna resposta e fontes oficiais.
- **Áudio de entrada:** o navegador grava até 60 segundos com `MediaRecorder`.
  O arquivo é enviado ao Whisper local (`POST /api/stt`, porta 8002), e a
  transcrição aparece no campo de texto para revisão antes do envio ao assistente.
- **Áudio de saída:** ao selecionar **Ouvir resposta**, o texto da resposta é
  limpo da marcação Markdown, dividido em trechos de até 500 caracteres e
  sintetizado pelo Piper local (`POST /api/tts`, porta 8001). Não há reprodução
  automática.

Ambas as modalidades usam a mesma API de orientação e a mesma busca RAG
(`bge-m3` + ChromaDB); a fala é transcrita para texto antes da interpretação.
Nenhum áudio é enviado ao Gemini ou gravado em disco.

## Fluxo de demonstração

1. Inicie o Ollama com `bge-m3`, o back-end configurado, o STT e o TTS; depois
   inicie o Next.js. O [guia Windows](../Como_executar_win.md) contém os comandos
   de instalação, portas e verificação de saúde.
2. Envie uma pergunta digitada, por exemplo: “Quais critérios do Auxílio Gás
   devo confirmar?”. Registre a orientação e as fontes exibidas.
3. Clique no microfone, pergunte em voz alta sobre outro benefício e pare a
   gravação. Confira a transcrição, edite-a se necessário e envie.
4. Confira que a resposta da fala segue o mesmo fluxo RAG, aparece formatada
   (títulos, listas, negrito e itálico) e apresenta fontes oficiais.
5. Selecione **Ouvir resposta** e depois **Parar áudio** para demonstrar a
   síntese local.

**Evidências para a entrega:** capture uma tela da transcrição antes do envio,
uma tela da resposta formatada com as fontes e outra durante a reprodução. Não
inclua chaves, dados pessoais ou gravações de terceiros.

## Limitações conhecidas

- Somente português é configurado no Whisper. Ruído, microfones e sotaques
  podem afetar a transcrição; sempre revise o texto antes de enviar.
- A transcrição é feita após parar a gravação (não há prévia ao vivo). O limite
  do serviço é 60 segundos e 8 MiB por arquivo.
- Whisper e Piper rodam localmente em CPU; a primeira inicialização e a síntese
  podem demorar. Trechos de áudio podem ter pequenas pausas.
- É necessário permitir o microfone em `localhost` ou HTTPS. Sem suporte ou
  permissão, a entrada digitada permanece disponível.
- O backend principal ainda precisa de um provedor configurado. No fluxo de
  entrada de voz, apenas o texto transcrito é encaminhado a ele.
- PDF, imagem e vídeo não são modalidades desta entrega; a interface não armazena
  áudio nem mantém histórico persistente de conversas.

## Falhas identificadas e mitigação

| Falha | Mitigação |
| --- | --- |
| Microfone negado, indisponível ou navegador incompatível | Exibir orientação para conceder permissão; permitir digitação. |
| Transcrição vazia ou incompreensível | Não enviar automaticamente; pedir nova gravação e permitir edição manual. |
| Áudio maior que 60 s/8 MiB ou formato não aceito | Parar a gravação no limite e orientar a dividir a pergunta. |
| Whisper indisponível/ocupado (503/429) | Mostrar erro, manter a pergunta editável e permitir tentar novamente. |
| Piper indisponível/ocupado (503/429) | Mostrar erro sem interromper o texto; permitir repetir a leitura. |
| Áudio reproduzido sem som ou bloqueado | Manter reprodução iniciada pelo usuário e mostrar erro para verificar volume/navegador. |
| Resposta do assistente indisponível | Manter erro explícito e orientar a revisar a configuração do backend; não simular resposta. |

## Demonstração CLI existente

Na raiz do projeto, com o ambiente Python ativado:

```powershell
python multimodalidade\demo_multimodal.py "Quais benefícios existem para gestantes?" --modalidade texto
python multimodalidade\demo_multimodal.py "Como funciona o Bolsa Família" --modalidade audio
python multimodalidade\demo_multimodal.py "Quais critérios para o BPC" --modalidade audio --falar
```

O fluxo web usa os serviços STT/TTS locais descritos em
[`Dados-RAG/RAG/STT.md`](../Dados-RAG/RAG/STT.md) e
[`Dados-RAG/RAG/TTS.md`](../Dados-RAG/RAG/TTS.md); o CLI acima continua sendo
uma demonstração separada.
