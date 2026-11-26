"""Coach de Conversa: CLI interativa.  Uso:  python -m coach"""

from __future__ import annotations

import shlex
import sys

import anthropic

from . import llm, memoria
from .personas import CANAIS, PERSONAS, system_simulacao
from .prompts import EXTRACAO_SCHEMA, EXTRACAO_SYSTEM, system_para

AJUDA = """
Comandos
  /perfil                 configura seu perfil (estilo, interesses, objetivo)
  /contato <nome>         escolhe (ou cria) a pessoa com quem você está conversando
  /contatos               lista contatos salvos e o que o coach lembra de cada um
  /nota <texto>           salva uma anotação sobre o contato atual

  /analisar [prints...]   cola uma conversa (ou passa prints) e recebe análise + 3 respostas
  /responder              cola a última mensagem dela e recebe 3 opções rápidas
  /encontro               planeja o encontro e escreve o convite
  /pos                    conta como foi o encontro e decide o próximo passo
  /bio [fotos...]         revisa sua bio/fotos do app ou Instagram

  /simular                treino: conversa com uma personagem fictícia
  /fim                    encerra o treino e recebe o feedback com notas

  /coach                  volta para conversa livre com o coach
  /ajuda   /sair
Para colar textos com várias linhas: cole e termine com uma linha só com FIM.
"""


class Sessao:
    """Uma conversa com o modelo dentro de um modo (system prompt + histórico)."""

    def __init__(self, modo: str, system: str, effort: str = "medium", prefixo: str = "\nCoach: "):
        self.modo = modo
        self.system = system
        self.effort = effort
        self.prefixo = prefixo
        self.historico: list[dict] = []

    def enviar(self, conteudo) -> str:
        self.historico.append({"role": "user", "content": conteudo})
        try:
            content = llm.stream_reply(self.system, self.historico, self.effort, self.prefixo)
        except anthropic.APIStatusError as e:
            self.historico.pop()
            print(f"\n[Erro da API {e.status_code}: {e.message}]")
            return ""
        except anthropic.APIConnectionError:
            self.historico.pop()
            print("\n[Sem conexão com a API. Tente de novo.]")
            return ""
        # Anexa o content completo, sem editar, para preservar o histórico como veio.
        self.historico.append({"role": "assistant", "content": content})
        return "".join(b.text for b in content if b.type == "text")


class App:
    def __init__(self):
        self.perfil = memoria.carregar_perfil()
        self.contato: dict | None = None
        self.sessao = self._nova("coach")
        self.sim_info: tuple[str, str] | None = None

    # ---------- utilidades ----------

    def _nova(self, modo: str) -> Sessao:
        return Sessao(modo, system_para(modo, memoria.perfil_texto(self.perfil)))

    def _contexto_contato(self) -> str:
        if not self.contato:
            return ""
        return "Contexto que você já sabe sobre ela:\n" + memoria.contato_texto(self.contato) + "\n\n"

    @staticmethod
    def ler_multilinha(instrucao: str) -> str:
        print(instrucao + "  (termine com uma linha: FIM)")
        linhas = []
        while True:
            try:
                linha = input()
            except EOFError:
                break
            if linha.strip().upper() == "FIM":
                break
            linhas.append(linha)
        return "\n".join(linhas).strip()

    @staticmethod
    def _imagens(caminhos: list[str]) -> list[dict]:
        blocos = []
        for c in caminhos:
            try:
                blocos.append(llm.image_block(c))
            except (OSError, ValueError) as e:
                print(f"[Ignorando {c}: {e}]")
        return blocos

    def _rotulo(self) -> str:
        if self.sessao.modo == "simulacao" and self.sim_info:
            return f"treino:{self.sim_info[0]}"
        nome = f"@{self.contato['nome']}" if self.contato else ""
        return f"{self.sessao.modo}{nome}"

    # ---------- comandos ----------

    def cmd_perfil(self, _args):
        print("\nVamos montar seu perfil. Enter mantém o valor atual.\n")
        for chave, pergunta in memoria.CAMPOS_PERFIL:
            atual = self.perfil.get(chave, "")
            if chave == "exemplos":
                print(f"{pergunta}" + (f"\n  (atual: {atual[:80]}...)" if atual else ""))
                valor = self.ler_multilinha("")
            else:
                valor = input(f"{pergunta}" + (f" [{atual}]" if atual else "") + " ").strip()
            if valor:
                self.perfil[chave] = valor
        memoria.salvar_perfil(self.perfil)
        self.sessao = self._nova(self.sessao.modo if self.sessao.modo != "simulacao" else "coach")
        print("\n✔ Perfil salvo. O coach vai usar isso para soar como você.")

    def cmd_contato(self, args):
        if not args:
            print("Uso: /contato <nome>")
            return
        nome = " ".join(args)
        self.contato = memoria.carregar_contato(nome)
        if not memoria.caminho_contato(nome).exists():
            onde = input(f"Onde você conheceu {nome} / por onde conversam? ").strip()
            self.contato["onde"] = onde
            memoria.salvar_contato(self.contato)
            print(f"✔ Contato {nome} criado.")
        else:
            print(f"✔ Contato atual: {nome}\n" + memoria.contato_texto(self.contato))

    def cmd_contatos(self, _args):
        contatos = memoria.listar_contatos()
        if not contatos:
            print("Nenhum contato ainda. Use /contato <nome>.")
        for c in contatos:
            ult = c.get("historico", ["—"])[-1] if c.get("historico") else "—"
            print(f"• {c.get('nome')}  (interesse: {c.get('interesse_nivel')})  {ult}")

    def cmd_nota(self, args):
        if not self.contato:
            print("Escolha um contato antes: /contato <nome>")
            return
        self.contato.setdefault("notas", []).append(" ".join(args))
        memoria.salvar_contato(self.contato)
        print("✔ Nota salva.")

    def cmd_analisar(self, args):
        imagens = self._imagens(args)
        texto = "" if imagens else self.ler_multilinha("Cole a conversa (indique quem é quem):")
        if not texto and not imagens:
            return
        self.sessao = self._nova("analisar")
        pedido = self._contexto_contato() + "Analise esta conversa:\n\n" + (texto or "(veja os prints)")
        self.sessao.enviar(imagens + [{"type": "text", "text": pedido}])
        if self.contato:
            self._atualizar_memoria(texto, imagens)

    def _atualizar_memoria(self, texto: str, imagens: list[dict]):
        if imagens and not texto:
            # A extração usa só texto: aproveita a transcrição que o coach já viu nos prints.
            texto = "(conversa enviada em prints; use a análise abaixo)\n" + "".join(
                b.text for m in self.sessao.historico if m["role"] == "assistant"
                for b in m["content"] if b.type == "text"
            )
        ext = llm.extract_json(EXTRACAO_SYSTEM, f"Conversa com {self.contato['nome']}:\n\n{texto}",
                               EXTRACAO_SCHEMA)
        if ext:
            memoria.mesclar_extracao(self.contato, ext)
            memoria.salvar_contato(self.contato)
            print(f"\n🧠 Memória de {self.contato['nome']} atualizada.")

    def cmd_responder(self, _args):
        texto = self.ler_multilinha("Cole a(s) última(s) mensagem(ns) dela:")
        if not texto:
            return
        self.sessao = self._nova("responder")
        self.sessao.enviar(self._contexto_contato() + "Última(s) mensagem(ns) dela:\n" + texto)

    def _modo_conversado(self, modo: str, abertura: str):
        self.sessao = self._nova(modo)
        extra = input(abertura + " ").strip()
        self.sessao.enviar(self._contexto_contato() + (extra or "Vamos começar."))

    def cmd_encontro(self, _args):
        self._modo_conversado("encontro", "Conta o contexto (cidade, orçamento, ideias, dia possível):")

    def cmd_pos(self, _args):
        self.sessao = self._nova("pos")
        relato = self.ler_multilinha("Como foi o encontro? Conte com detalhes:")
        if relato:
            self.sessao.enviar(self._contexto_contato() + relato)

    def cmd_bio(self, args):
        imagens = self._imagens(args)
        texto = self.ler_multilinha("Cole sua bio (ou só FIM se mandou apenas fotos):")
        self.sessao = self._nova("bio")
        self.sessao.enviar(imagens + [{"type": "text", "text": "Minha bio:\n" + (texto or "(sem bio)")}])

    def cmd_simular(self, _args):
        ids = list(PERSONAS)
        print("\nPersonagens:")
        for i, pid in enumerate(ids, 1):
            print(f"  {i}. {PERSONAS[pid]['titulo']}")
        escolha = input("Número da personagem: ").strip()
        canais = list(CANAIS)
        print("Canal:  " + "  ".join(f"{i}. {c}" for i, c in enumerate(canais, 1)))
        canal = input("Número do canal: ").strip()
        try:
            pid = ids[int(escolha) - 1]
            cid = canais[int(canal) - 1]
        except (ValueError, IndexError):
            print("Opção inválida.")
            return
        nome = PERSONAS[pid]["titulo"].split(",")[0]
        self.sim_info = (pid, cid)
        self.sessao = Sessao("simulacao", system_simulacao(pid, cid), effort="low", prefixo=f"\n{nome}: ")
        print(f"\n🎭 Treino iniciado com {nome} ({cid}). Você começa. /fim para encerrar e ver o feedback.\n")

    def cmd_fim(self, _args):
        if self.sessao.modo != "simulacao" or not self.sessao.historico:
            print("Nenhum treino em andamento. Use /simular.")
            return
        pid, cid = self.sim_info
        nome = PERSONAS[pid]["titulo"].split(",")[0]
        linhas = []
        for m in self.sessao.historico:
            quem = "Usuário" if m["role"] == "user" else nome
            txt = m["content"] if isinstance(m["content"], str) else "".join(
                b.text for b in m["content"] if b.type == "text")
            linhas.append(f"{quem}: {txt}")
        transcricao = "\n".join(linhas)
        self.sessao = self._nova("feedback")
        self.sim_info = None
        self.sessao.enviar(
            f"Personagem: {PERSONAS[pid]['descricao']}\nCanal: {CANAIS[cid]}\n\nTranscrição:\n{transcricao}"
        )
        print("\n(Continue perguntando ao coach sobre o treino, ou /simular para outro.)")

    def cmd_coach(self, _args):
        self.sessao = self._nova("coach")
        print("Modo conversa livre.")

    # ---------- loop ----------

    def run(self):
        print("💘 Coach de Conversa (/ajuda para comandos)")
        if not self.perfil:
            print("Dica: comece com /perfil para o coach aprender seu jeito de falar.")
        comandos = {
            "perfil": self.cmd_perfil, "contato": self.cmd_contato, "contatos": self.cmd_contatos,
            "nota": self.cmd_nota, "analisar": self.cmd_analisar, "responder": self.cmd_responder,
            "encontro": self.cmd_encontro, "pos": self.cmd_pos, "bio": self.cmd_bio,
            "simular": self.cmd_simular, "fim": self.cmd_fim, "coach": self.cmd_coach,
        }
        while True:
            try:
                entrada = input(f"\n[{self._rotulo()}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAté mais! 👋")
                return
            if not entrada:
                continue
            if entrada.startswith("/"):
                try:
                    partes = shlex.split(entrada[1:])
                except ValueError:
                    partes = entrada[1:].split()
                cmd, args = (partes[0].lower(), partes[1:]) if partes else ("", [])
                if cmd in ("sair", "exit", "quit"):
                    print("Até mais! 👋")
                    return
                if cmd == "ajuda":
                    print(AJUDA)
                elif cmd in comandos:
                    try:
                        comandos[cmd](args)
                    except KeyboardInterrupt:
                        print("\n[Interrompido]")
                else:
                    print("Comando desconhecido. /ajuda")
                continue
            try:
                self.sessao.enviar(entrada)
            except KeyboardInterrupt:
                print("\n[Interrompido]")


def main():
    try:
        App().run()
    except anthropic.AuthenticationError:
        print("Credencial inválida. Defina ANTHROPIC_API_KEY (veja o README).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
