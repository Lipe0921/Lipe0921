#!/usr/bin/env python3
"""Motor dos jogos do perfil: jogo da velha e pedra, papel e tesoura.

O workflow jogos.yml chama este script quando alguém abre uma issue com o
título "velha|<1-9>" ou "ppt|<pedra|papel|tesoura>". O título vem de fora,
então é tratado como dado não confiável: só é aceito se bater exatamente com
os padrões abaixo, e nunca é passado para um shell.
"""
import json
import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import quote

REPO = os.environ.get("GITHUB_REPOSITORY", "Lipe0921/Lipe0921")
DONO = REPO.split("/")[0]
RAIZ = Path(__file__).resolve().parents[2]
ESTADO = RAIZ / "jogos" / "estado.json"
README = RAIZ / "README.md"
INICIO = "<!-- JOGOS:START -->"
FIM = "<!-- JOGOS:END -->"

LINHAS = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
          (0, 3, 6), (1, 4, 7), (2, 5, 8),
          (0, 4, 8), (2, 4, 6)]
CHANCE_ERRO_BOT = 0.25   # o bot às vezes joga aleatório, para dar para ganhar
MAX_HISTORICO = 5

EMOJI = {"pedra": "🪨", "papel": "📄", "tesoura": "✂️"}
VENCE = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}


# ---------- estado ----------
def placar_zerado():
    return {"visitantes": 0, "bot": 0, "empates": 0}


def estado_inicial():
    return {
        "velha": {"tabuleiro": [" "] * 9, "placar": placar_zerado(), "historico": []},
        "ppt": {"placar": placar_zerado(), "historico": []},
    }


def carregar():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return estado_inicial()


def salvar(est):
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def perfil(user):
    if user == "visitante":
        return "um visitante"
    return f"[@{user}](https://github.com/{user})"


def registrar(historico, texto):
    historico.insert(0, texto)
    del historico[MAX_HISTORICO:]


# ---------- jogo da velha ----------
def vencedor(t):
    for a, b, c in LINHAS:
        if t[a] != " " and t[a] == t[b] == t[c]:
            return t[a]
    return "empate" if " " not in t else None


def jogada_bot(t):
    vazias = [i for i, c in enumerate(t) if c == " "]
    if random.random() < CHANCE_ERRO_BOT:
        return random.choice(vazias)
    for simbolo in ("O", "X"):          # ganhar, depois bloquear
        for i in vazias:
            teste = t[:]
            teste[i] = simbolo
            if vencedor(teste) == simbolo:
                return i
    if 4 in vazias:
        return 4
    cantos = [i for i in (0, 2, 6, 8) if i in vazias]
    return random.choice(cantos or vazias)


def jogar_velha(est, user, arg):
    v = est["velha"]
    if not re.fullmatch(r"[1-9]", arg):
        return "Jogada inválida. Use um número de 1 a 9."
    i = int(arg) - 1
    t = v["tabuleiro"]
    if t[i] != " ":
        return f"A casa **{i + 1}** já está ocupada. Escolha outra no perfil."

    t[i] = "X"
    resultado = vencedor(t)
    bot = None
    if resultado is None:
        bot = jogada_bot(t)
        t[bot] = "O"
        resultado = vencedor(t)

    msg = f"Você jogou na casa **{i + 1}**."
    if bot is not None:
        msg += f" O bot respondeu na casa **{bot + 1}**."
    if resultado is None:
        return msg + " A partida continua! Volte ao perfil e faça sua próxima jogada."

    if resultado == "X":
        v["placar"]["visitantes"] += 1
        registrar(v["historico"], f"🎉 {perfil(user)} venceu o bot")
        fim = "🎉 **Você venceu o bot!**"
    elif resultado == "O":
        v["placar"]["bot"] += 1
        registrar(v["historico"], f"🤖 o bot venceu {perfil(user)}")
        fim = "🤖 **O bot venceu desta vez.** Tente de novo!"
    else:
        v["placar"]["empates"] += 1
        registrar(v["historico"], f"🤝 {perfil(user)} empatou com o bot")
        fim = "🤝 **Deu velha!** Empate."
    v["tabuleiro"] = [" "] * 9
    return f"{msg} {fim} Já começou uma nova partida no perfil."


# ---------- pedra, papel e tesoura ----------
def jogar_ppt(est, user, arg):
    p = est["ppt"]
    if arg not in EMOJI:
        return "Opção inválida. Use pedra, papel ou tesoura."
    bot = random.choice(list(EMOJI))
    duelo = f"{EMOJI[arg]} {arg} × {EMOJI[bot]} {bot}"
    if arg == bot:
        p["placar"]["empates"] += 1
        registrar(p["historico"], f"🤝 {perfil(user)}: {duelo}, empate")
        return f"Você: {EMOJI[arg]} **{arg}**. Bot: {EMOJI[bot]} **{bot}**. 🤝 **Empate!**"
    if VENCE[arg] == bot:
        p["placar"]["visitantes"] += 1
        registrar(p["historico"], f"🎉 {perfil(user)}: {duelo}, venceu")
        return f"Você: {EMOJI[arg]} **{arg}**. Bot: {EMOJI[bot]} **{bot}**. 🎉 **Você venceu!**"
    p["placar"]["bot"] += 1
    registrar(p["historico"], f"🤖 {perfil(user)}: {duelo}, o bot venceu")
    return f"Você: {EMOJI[arg]} **{arg}**. Bot: {EMOJI[bot]} **{bot}**. 🤖 **O bot venceu!**"


# ---------- README ----------
def link_issue(titulo):
    corpo = ("Basta clicar em Submit new issue. Não altere o título! "
             "O bot joga e o placar atualiza sozinho.")
    return (f"https://github.com/{REPO}/issues/new"
            f"?title={quote(titulo, safe='')}&body={quote(corpo, safe='')}")


def placar_txt(p):
    return (f"👥 Visitantes **{p['visitantes']}** · "
            f"🤖 Bot **{p['bot']}** · 🤝 Empates **{p['empates']}**")


def historico_txt(h):
    if not h:
        return "<sub>Ninguém jogou ainda. Seja a primeira pessoa! 🚀</sub>"
    itens = "\n".join(f"- {x}" for x in h)
    return ("<details>\n<summary><sub>Últimos resultados</sub></summary>\n\n"
            f"{itens}\n\n</details>")


def tabuleiro_txt(t):
    simbolo = {"X": "❌", "O": "⭕"}
    cel = [simbolo[c] if c != " " else f"[⬜]({link_issue(f'velha|{i + 1}')})"
           for i, c in enumerate(t)]
    linhas = ["| | | |", "|:-:|:-:|:-:|"]
    linhas += [f"| {cel[r * 3]} | {cel[r * 3 + 1]} | {cel[r * 3 + 2]} |" for r in range(3)]
    return "\n".join(linhas)


def render_tudo(est):
    v, p = est["velha"], est["ppt"]
    opcoes = " · ".join(f"[{EMOJI[o]} {o.capitalize()}]({link_issue(f'ppt|{o}')})"
                        for o in EMOJI)
    return f"""### ❌⭕ Jogo da velha (você é o ❌)

<div align="center">

{tabuleiro_txt(v['tabuleiro'])}

{placar_txt(v['placar'])}

{historico_txt(v['historico'])}

</div>

### ✊ Pedra, papel e tesoura

<div align="center">

{opcoes}

{placar_txt(p['placar'])}

{historico_txt(p['historico'])}

</div>"""


def atualizar_readme(est):
    texto = README.read_text(encoding="utf-8")
    if INICIO not in texto or FIM not in texto:
        raise SystemExit("Marcadores JOGOS:START/END não encontrados no README.md")
    padrao = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIM), re.S)
    novo = f"{INICIO}\n{render_tudo(est)}\n{FIM}"
    README.write_text(padrao.sub(lambda _: novo, texto, count=1), encoding="utf-8")


# ---------- entrada ----------
def main():
    est = carregar()
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        salvar(est)
        atualizar_readme(est)
        print("README e estado inicializados")
        return

    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        evento = json.load(f)
    issue = evento["issue"]
    titulo = (issue.get("title") or "").strip().lower()
    user = (issue.get("user") or {}).get("login", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", user):
        user = "visitante"

    m = re.fullmatch(r"(velha|ppt)\|([a-z0-9]{1,10})", titulo)
    if not m:
        resposta = "Título inválido. Use os links do perfil para jogar."
    elif m.group(1) == "velha":
        resposta = jogar_velha(est, user, m.group(2))
    else:
        resposta = jogar_ppt(est, user, m.group(2))

    salvar(est)
    atualizar_readme(est)

    comentario = (f"{resposta}\n\nVeja o placar atualizado no "
                  f"[perfil](https://github.com/{DONO}) (leva uns segundos). 🎮\n")
    destino = os.environ.get("COMMENT_FILE")
    if destino:
        Path(destino).write_text(comentario, encoding="utf-8")
    print(comentario)


if __name__ == "__main__":
    main()
