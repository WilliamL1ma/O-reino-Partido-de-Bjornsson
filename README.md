# O Reino Partido de Bjornsson

Aplicacao web de RPG narrativo ambientada em Elandoria, com cadastro de jogadores, criacao de personagem, persistencia em PostgreSQL e um mestre conversacional opcional apoiado por Groq + LangGraph.

O projeto combina:

- backend em Flask
- frontend server-rendered em HTML, CSS e JavaScript puro
- banco PostgreSQL com SQLAlchemy + Alembic
- motor narrativo com cenas, combates, puzzle e memoria persistida

## Sumario

- [Visao geral](#visao-geral)
- [O que o projeto entrega](#o-que-o-projeto-entrega)
- [Fluxo do jogador](#fluxo-do-jogador)
- [Arquitetura](#arquitetura)
- [Rotas principais](#rotas-principais)
- [Estrutura do repositorio](#estrutura-do-repositorio)
- [Execucao local](#execucao-local)
- [Variaveis de ambiente](#variaveis-de-ambiente)
- [Docker](#docker)
- [Testes](#testes)
- [Modo com e sem Groq](#modo-com-e-sem-groq)
- [Estado atual e limitacoes](#estado-atual-e-limitacoes)

## Visao geral

O jogo apresenta o universo de **O Reino Partido de Bjornsson** a partir do presente do reino de **Elandoria**. O jogador cria um personagem, escolhe raca, rola atributos, define uma classe e entra em uma jornada guiada pelo "Mestre de Elandoria".

Hoje o projeto ja possui uma base funcional de produto e nao apenas uma landing page:

- autenticacao de usuario
- onboarding completo do personagem
- Capitulo I jogavel
- inventario, XP e ouro persistidos
- chat com mestre narrativo
- rolagens pendentes com consequencia separada
- sugestoes de acoes
- memoria narrativa resumida
- testes para backend, fluxo narrativo e partes do frontend

## O que o projeto entrega

- landing page publica, login e registro
- criacao de ficha com nome, idade, personalidade, objetivo e medo
- selecao de raca, incluindo racas especiais com d20
- rolagem sequencial de 7 atributos
- selecao de classe com validacao por requisitos
- area do jogador e ficha completa
- Capitulo I em Elandoria com atos, encontros e puzzle
- drops, XP, ouro e janela de loot pos-combate
- reset de campanha mantendo a ficha
- migracoes automaticas ao iniciar a aplicacao
- Docker Compose para app + banco

Catalogo atual do jogo:

- 10 racas
- 12 classes
- 7 atributos
- 4 tatics de encontro
- 11 monstros catalogados

## Fluxo do jogador

1. O usuario cria a conta em `/registro` e faz login em `/login`.
2. A aplicacao redireciona para `/jogador/ficha`.
3. O jogador escolhe uma raca em `/jogador/raca`.
4. `Anjo` e `Demonio` dependem de uma rolagem especial:
   - `Anjo`: `15+`
   - `Demonio`: `16+`
5. O jogador rola `FOR`, `DEX`, `CON`, `INT`, `SAB`, `CAR` e `PER`.
6. O sistema libera apenas as classes cujos requisitos foram atendidos.
7. Depois da classe escolhida, o personagem entra em `/jogo`.
8. A campanha alterna entre:
   - escolhas de cena
   - encontros
   - conversa livre com o mestre
   - atualizacao de inventario, XP, ouro e estado narrativo

Resumo do Capitulo I:

- **Ato 1**: `chapter_entry`, `encounter_goblin`, `encounter_robalo`
- **Ato 2**: `act_two_crossroads`, `encounter_duende`, `encounter_cobra`, `encounter_raposa`
- **Ato 3**: `act_three_threshold`, `encounter_aranha`, `encounter_lupus`, `encounter_passaro`
- **Ato 4**: `freya_legacy`
- **Ato 5**: `encounter_lobisomem`, `chapter_complete`

Ao concluir o capitulo, o personagem recebe o `Cristal Incompreendido` e um legado ligado a Rowan ou Freya, dependendo do perfil da classe.

## Arquitetura

### Stack

| Camada | Tecnologia |
| --- | --- |
| Backend web | Flask 3 |
| ORM | SQLAlchemy 2 |
| Migracoes | Alembic |
| Banco | PostgreSQL |
| Senhas | bcrypt |
| LLM gateway | Groq |
| Orquestracao narrativa | LangGraph |
| Frontend | HTML + CSS + JavaScript puro |
| Servidor em container | gunicorn |

### Visao rapida

```mermaid
flowchart LR
    A[Frontend HTML CSS JS] --> B[Flask]
    B --> C[Blueprints auth player game]
    C --> D[(PostgreSQL)]
    C --> E[Narrative Services]
    E --> F[LangGraph Master Graph]
    F --> G[Groq opcional]
```

### Componentes principais

- `backend/app.py`
  - carrega `.env`, registra blueprints e roda migracoes antes de subir o servidor
- `backend/web_blueprints/`
  - separa rotas de autenticacao, jogador e jogo
- `backend/narrative/`
  - concentra estado, memoria, rolagem, sugestoes e ciclo do mestre
- `backend/master_graph.py`
  - organiza geracao, revisao, fallback e finalizacao do pipeline narrativo
- `frontend/game_play.html` + `frontend/script.js`
  - renderizam a interface principal e sincronizam a cena sem hard reload

O pipeline do mestre, em alto nivel, segue este caminho:

```text
prepare_state -> mechanics -> narrative_generate -> review/revise/fallback -> suggestions -> finalize
```

Comportamentos importantes:

- eventos mecanicos podem bloquear sugestoes
- o sistema possui fallbacks quando a camada LLM falha
- sugestoes passam por sanitizacao antes de chegar ao jogador
- rolagem e consequencia sao separadas para melhorar a UX do modal

## Rotas principais

### Paginas

| Rota | Funcao |
| --- | --- |
| `/` | landing page |
| `/login` | login |
| `/registro` | cadastro |
| `/jogador` | area do jogador |
| `/jogador/ficha` | criacao da ficha |
| `/jogador/raca` | selecao de raca |
| `/jogador/status` | rolagem de atributos |
| `/jogador/classe` | selecao de classe |
| `/jogador/ficha-completa` | ficha consolidada |
| `/jogo` | tela principal do gameplay |

### Acoes

| Rota | Metodo | Funcao |
| --- | --- | --- |
| `/logout` | `POST` | encerra sessao |
| `/jogador/status/rolar-modal` | `POST` | rola os atributos no modal |
| `/jogador/raca/rolar` | `POST` | resolve raca especial |
| `/jogo/mestre` | `POST` | envia mensagem ao mestre |
| `/jogo/rolar` | `POST` | inicia a rolagem pendente |
| `/jogo/rolar/consequencia` | `POST` | devolve a consequencia narrativa |
| `/jogo/resetar-campanha` | `POST` | reinicia o capitulo mantendo a ficha |

## Estrutura do repositorio

```text
.
|-- backend/
|   |-- app.py
|   |-- app_factory.py
|   |-- database.py
|   |-- models.py
|   |-- game_content.py
|   |-- master_graph.py
|   |-- master_pipeline/
|   |-- narrative/
|   |-- web_blueprints/
|   `-- web_support/
|-- frontend/
|   |-- index.html
|   |-- login.html
|   |-- register.html
|   |-- character_create.html
|   |-- race_select.html
|   |-- status_page.html
|   |-- class_select.html
|   |-- player_home.html
|   |-- character_sheet.html
|   |-- game_play.html
|   |-- script.js
|   |-- game_ui_helpers.js
|   `-- styles.css
|-- alembic/
|-- tests/
|-- docker-compose.yml
|-- Dockerfile
`-- requirements.txt
```

## Execucao local

### Pre-requisitos

- Python 3.12 recomendado
- PostgreSQL 16 recomendado
- Node 18+ opcional para o teste JS
- Docker opcional

### 1. Criar ambiente virtual

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

### 2. Configurar o banco

Voce pode usar um PostgreSQL local ou subir apenas o banco pelo Compose:

```powershell
docker compose up -d db
```

### 3. Criar o `.env`

```env
SECRET_KEY=troque-por-uma-chave-segura
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=bjornsson
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Opcional: habilita o mestre conversacional
GROQ_API_KEY=sua-chave-aqui
```

Se preferir, `DATABASE_URL` pode substituir os `POSTGRES_*`.

### 4. Rodar a aplicacao

```powershell
py backend/run.py
```

Ao iniciar localmente, a aplicacao:

1. espera o banco ficar disponivel
2. executa `alembic upgrade head`
3. sobe o servidor Flask

Padrao local:

- app: `http://127.0.0.1:8000`
- banco: `127.0.0.1:5432`

### 5. Rodar apenas migracoes

```powershell
py backend/migrate.py
```

## Variaveis de ambiente

| Variavel | Default | Uso |
| --- | --- | --- |
| `SECRET_KEY` | `dev-secret-key` | chave de sessao do Flask |
| `DATABASE_URL` | vazio | URL completa do banco |
| `POSTGRES_HOST` | `127.0.0.1` | host do banco |
| `POSTGRES_PORT` | `5432` | porta do banco |
| `POSTGRES_DB` | `bjornsson` | nome do banco |
| `POSTGRES_USER` | `postgres` | usuario do banco |
| `POSTGRES_PASSWORD` | `postgres` | senha do banco |
| `DB_CONNECT_RETRIES` | `20` | tentativas de conexao |
| `DB_CONNECT_DELAY` | `1.5` | intervalo entre tentativas |
| `FLASK_HOST` | `127.0.0.1` | host do app |
| `FLASK_PORT` | `8000` | porta do app |
| `FLASK_DEBUG` | `true` | modo debug |
| `GROQ_API_KEY` | vazio | habilita o mestre conversacional |
| `GROQ_MODEL_NARRATIVE` | `qwen/qwen3-32b` | modelo narrativo |
| `GROQ_MODEL_FAST` | `llama-3.1-8b-instant` | modelo rapido |
| `GROQ_TIMEOUT_SECONDS` | `25.0` | timeout global da Groq |
| `GROQ_MAX_TOKENS` | `700` | limite global de tokens |
| `TOTP_ISSUER_NAME` | vazio | legado reservado para futura expansao de 2FA |

## Docker

Para subir app + PostgreSQL:

```powershell
docker compose up -d --build
```

Para derrubar:

```powershell
docker compose down
```

Para derrubar e remover o volume do banco:

```powershell
docker compose down -v
```

Servicos:

- `bjornsson-db`: PostgreSQL 16 Alpine com volume persistente
- `bjornsson-app`: Python 3.12 Slim, migracoes e `gunicorn`

## Testes

Testes Python:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Teste JavaScript do helper de UI:

```powershell
node --test tests/test_frontend_roll_modal.js
```

A suite cobre:

- fluxo de cenas e transicoes
- pipeline do mestre
- runtime do gateway Groq
- rotas do backend
- servico de rolagem
- sincronizacao do frontend
- lifecycle do modal de rolagem

## Modo com e sem Groq

| Recurso | Sem `GROQ_API_KEY` | Com `GROQ_API_KEY` |
| --- | --- | --- |
| Onboarding e campanha estruturada | sim | sim |
| Encontros, drops, XP e ouro | sim | sim |
| Tela principal do jogo | sim | sim |
| Chat em `/jogo/mestre` | nao | sim |
| Intro dinamica do mestre | fallback local | sim |
| Sugestoes narrativas | fallback local | sim |
| Resumo de memoria com LLM | nao | sim |

Na pratica:

- sem Groq, o projeto continua jogavel como experiencia guiada
- com Groq, a experiencia fica mais conversacional e flexivel

## Estado atual e limitacoes

- o projeto esta concentrado no Capitulo I, embora a base permita expansao
- parte do estado narrativo fica serializada em texto na tabela `characters`
- o frontend e propositalmente simples, sem framework de componentes
- o README antigo citava `2FA com TOTP e QR code`, mas isso nao esta integrado ao fluxo atual
- existem campos de 2FA no modelo e no ambiente, mas nao ha validacao TOTP ativa no login

## Resumo tecnico rapido

- RPG web com Flask no backend e HTML/CSS/JS puro no frontend
- PostgreSQL, SQLAlchemy e Alembic para persistencia
- onboarding completo de personagem
- campanha inicial jogavel em Elandoria
- estado, inventario, XP, ouro e mensagens persistidos
- mestre conversacional opcional com Groq + LangGraph
