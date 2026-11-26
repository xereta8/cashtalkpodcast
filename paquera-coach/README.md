# 💘 Coach de Conversa

Um agente de terminal, feito com a API do Claude, que ajuda você a **manter conversas boas** com
mulheres em apps de namoro, Instagram, WhatsApp e pessoalmente. Ele não responde por você: ele
analisa, sugere mensagens no **seu** estilo e te treina.

## Instalação

```bash
cd paquera-coach
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sua-chave"   # https://console.anthropic.com
python -m coach
```

## O que ele faz

| Comando | Para quê |
|---|---|
| `/perfil` | Questionário rápido sobre você (interesses, humor, como você escreve, exemplos reais). O coach usa isso para soar como você. |
| `/contato Ana` | Escolhe ou cria a pessoa. O coach **lembra** o que ela contou: fatos, interesses e assuntos pendentes. |
| `/analisar` ou `/analisar print1.png print2.png` | Cole a conversa ou mande prints. Você recebe a temperatura da conversa, sinais de interesse, o que funciona e o que atrapalha, ganchos para aprofundar, 3 próximas mensagens e o próximo passo. A memória do contato é atualizada sozinha. |
| `/responder` | Cola a última mensagem dela e recebe 3 opções rápidas. |
| `/encontro` | Sugestão de programa, convites prontos e assuntos para levar na manga. |
| `/pos` | Conta como foi o encontro e recebe uma leitura honesta e a mensagem de depois. |
| `/bio [fotos]` | Revisão da bio e da ordem das fotos. |
| `/simular` | **Treino** com personagens fictícias, cada uma com personalidade e nível de interesse próprios, em 4 canais (app, Instagram, WhatsApp, ao vivo). O interesse dela sobe ou cai conforme você conversa. |
| `/fim` | Encerra o treino e mostra notas de 0 a 10 por critério, melhores momentos e reescritas do que dá para melhorar. |
| `/nota`, `/contatos`, `/coach`, `/ajuda`, `/sair` | Utilidades. |

Para colar textos com várias linhas, termine com uma linha contendo só `FIM`.

### Personagens de treino

- **Lara**, 27: irônica, odeia "oi, tudo bem?"
- **Bia**, 24: tímida no começo, se abre depois
- **Camila**, 31: ocupada e direta, quer convite logo
- **Júlia**, 26: extrovertida, gosta de papo profundo
- **Rafaela**, 29: pouco interessada; treina ler sinais e recuar com elegância

Para adicionar outras, edite `coach/personas.py`.

## Princípios

O coach é instruído a priorizar autenticidade, curiosidade genuína e respeito. Ele **não** sugere
manipulação, "negs", insistência depois de um não ou joguinhos. Isso é questão de ética e também
de resultado: essas táticas afastam as pessoas.

## Detalhes técnicos

- Modelo: `claude-opus-5-5` (troque com `COACH_MODEL=...`), com respostas em streaming.
- Fallback automático no servidor caso o modelo recuse um pedido (`fallbacks: "default"`, beta).
- A memória dos contatos é extraída com saída estruturada (JSON Schema).
- Os dados ficam **só na sua máquina**, em `paquera-coach/dados/` (ignorado pelo git; mude o
  local com `COACH_DADOS=...`). As conversas que você cola são enviadas à API da Anthropic para
  análise. Evite colar dados sensíveis de terceiros.

```
coach/
  __main__.py   CLI e comandos
  llm.py        chamadas à API (streaming, fallback, JSON, imagens)
  prompts.py    system prompts de cada modo
  personas.py   personagens e canais do treino
  memoria.py    perfil e memória dos contatos (JSON local)
```
