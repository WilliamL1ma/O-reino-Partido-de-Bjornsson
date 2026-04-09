# O Reino Partido de Bjornsson

Projeto inicial de apresentacao do RPG O Reino Partido de Bjornsson com:

- backend em Flask
- frontend em HTML, CSS e JavaScript
- landing page de convite para jogar a primeira parte
- Capítulo I centrado na origem do Reino de Elandoria
- autenticação com PostgreSQL para cadastro e login
- SQLAlchemy para ORM
- Alembic para migrações
- bcrypt para hash de senha
- 2FA com TOTP e QR code

## Executar

```bash
py -m pip install -r requirements.txt
py backend/run.py
```

O projeto le as configuracoes do arquivo `.env`.
Ao iniciar localmente, a aplicacao roda as migracoes do Alembic antes de subir o servidor Flask.

## Docker Desktop

Para subir a aplicacao Flask e o PostgreSQL em containers:

```bash
docker compose up -d --build
```

Para derrubar:

```bash
docker compose down
```

Para derrubar removendo tambem o volume do banco:

```bash
docker compose down -v
```

Servicos:

- app Flask: `http://127.0.0.1:8000`
- PostgreSQL: `127.0.0.1:5432`

Containers criados:

- `bjornsson-app`
- `bjornsson-db`

## PostgreSQL

Configure no `.env`:

```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=bjornsson
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SSLMODE=prefer
SECRET_KEY=troque-esta-chave-em-producao
TOTP_ISSUER_NAME=O Reino Partido de Bjornsson
```

Ao iniciar, a aplicacao executa `alembic upgrade head` e garante a estrutura do banco.

Abra `http://127.0.0.1:8000`.
