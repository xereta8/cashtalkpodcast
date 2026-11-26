"""Persistência local: perfil do usuário e memória de cada contato (JSON em ./dados)."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path

DADOS = Path(os.environ.get("COACH_DADOS", Path(__file__).resolve().parent.parent / "dados"))
PERFIL = DADOS / "perfil.json"
CONTATOS = DADOS / "contatos"

CAMPOS_PERFIL = [
    ("nome", "Como você se chama?"),
    ("idade", "Idade?"),
    ("cidade", "Cidade?"),
    ("profissao", "O que você faz da vida?"),
    ("interesses", "Hobbies e interesses (separados por vírgula)?"),
    ("personalidade", "Como seus amigos te descreveriam (ex.: engraçado, calmo, nerd)?"),
    ("estilo_escrita", "Como você costuma escrever? (curto/longo, gírias, emojis, 'kkk' ou 'haha')"),
    ("objetivo", "O que você procura (algo casual, namoro, ainda não sabe)?"),
    ("dificuldades", "Onde você sente que trava nas conversas?"),
    ("exemplos", "Cole 2–3 mensagens reais que você mandou (para o coach imitar seu jeito):"),
]


def _ler(path: Path, padrao):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def _gravar(path: Path, dados) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- Perfil ----------

def carregar_perfil() -> dict:
    return _ler(PERFIL, {})


def salvar_perfil(perfil: dict) -> None:
    _gravar(PERFIL, perfil)


def perfil_texto(perfil: dict) -> str:
    rotulos = dict(CAMPOS_PERFIL)
    linhas = [f"- {k}: {v}" for k, v in perfil.items() if v and k in rotulos]
    return "\n".join(linhas)


# ---------- Contatos ----------

def _slug(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "contato"


def caminho_contato(nome: str) -> Path:
    return CONTATOS / f"{_slug(nome)}.json"


def carregar_contato(nome: str) -> dict:
    return _ler(
        caminho_contato(nome),
        {"nome": nome, "onde": "", "fatos": [], "interesses": [], "ganchos": [],
         "interesse_nivel": "indefinido", "historico": [], "notas": []},
    )


def salvar_contato(contato: dict) -> None:
    _gravar(caminho_contato(contato["nome"]), contato)


def listar_contatos() -> list[dict]:
    if not CONTATOS.exists():
        return []
    return [_ler(p, {}) for p in sorted(CONTATOS.glob("*.json"))]


def _unir(lista: list[str], novos: list[str], limite: int = 40) -> list[str]:
    vistos = {x.casefold() for x in lista}
    for n in novos:
        if n and n.casefold() not in vistos:
            lista.append(n)
            vistos.add(n.casefold())
    return lista[-limite:]


def mesclar_extracao(contato: dict, ext: dict) -> None:
    contato["fatos"] = _unir(contato.get("fatos", []), ext.get("fatos", []))
    contato["interesses"] = _unir(contato.get("interesses", []), ext.get("interesses", []))
    # Ganchos são "o que está pendente agora": substitui pelos mais recentes.
    if ext.get("ganchos"):
        contato["ganchos"] = ext["ganchos"][:10]
    if ext.get("interesse_nivel") and ext["interesse_nivel"] != "indefinido":
        contato["interesse_nivel"] = ext["interesse_nivel"]
    if ext.get("resumo"):
        contato.setdefault("historico", []).append(f"{date.today().isoformat()}: {ext['resumo']}")
        contato["historico"] = contato["historico"][-20:]


def contato_texto(c: dict) -> str:
    if not c:
        return ""
    partes = [f"Nome: {c.get('nome')}"]
    if c.get("onde"):
        partes.append(f"Onde se conheceram / canal: {c['onde']}")
    for chave, rotulo in [("fatos", "Fatos"), ("interesses", "Interesses"),
                          ("ganchos", "Ganchos pendentes"), ("notas", "Notas do usuário"),
                          ("historico", "Histórico")]:
        if c.get(chave):
            partes.append(f"{rotulo}:\n" + "\n".join(f"  - {x}" for x in c[chave]))
    partes.append(f"Último nível de interesse percebido: {c.get('interesse_nivel', 'indefinido')}")
    return "\n".join(partes)
