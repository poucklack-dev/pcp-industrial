# PCP Industrial

Sistema web para planejamento e controle da produção, estoque, estruturas de produto e apontamentos industriais. A aplicação preserva a arquitetura Flask/Jinja existente e está sendo profissionalizada de forma incremental.

## Funcionalidades atuais

- autenticação e perfis de acesso;
- produtos MP, SA e PA;
- BOM multinível com bloqueio de circularidade, unidades e perdas;
- ordens de produção com transições de estado controladas;
- apontamentos parciais, consumo e entrada da produção boa;
- razão de movimentações e histórico de OP;
- dashboard, estoque, máquinas e relatórios;
- health check, proteção CSRF e headers HTTP de segurança;
- SQLite em desenvolvimento e PostgreSQL em produção.

## Início rápido com Docker

```bash
cp .env.example .env
# Troque SECRET_KEY e ADMIN_PASSWORD no .env
docker compose up --build
```

Acesse `http://localhost:5000`. O container aplica migrations e cria, de forma idempotente, dados fictícios de demonstração.

## Instalação local

Requer Python 3.12 ou superior.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
flask --app app db upgrade
flask --app app seed
flask --app app run
```

Em Linux/macOS, use `source .venv/bin/activate` e `cp` em vez de `copy`.

## Configuração

As variáveis estão em `.env.example`. `APP_ENV` aceita `development`, `testing` ou `production`. Em produção, `SECRET_KEY` é obrigatória e `DATABASE_URL` deve apontar para PostgreSQL:

```text
postgresql+psycopg://usuario:senha@host:5432/pcp
```

Nunca versione `.env` ou bancos locais. O comando `flask seed` usa somente identidades fictícias; personalize a senha administrativa por variável de ambiente.

## Banco e migrations

O banco não depende de `instance/pcp.db`. Para construir a estrutura do zero:

```bash
flask --app app db upgrade
flask --app app seed
```

`flask --app app init-db` existe apenas como conveniência local. O fluxo oficial e de produção é Alembic/Flask-Migrate.

Para uma instalação legada cujo esquema já existia antes das migrations, faça backup e execute uma única vez `flask --app app db stamp head`; bancos novos devem sempre usar `db upgrade`.

## Testes e qualidade

```bash
pytest
ruff check app.py config.py backend tests
```

O GitHub Actions executa ambos em cada `push` e `pull_request`.

## Arquitetura

```text
app.py                 factory, extensões, health e erros
config.py              configurações por ambiente
backend/               models, rotas, serviços e comandos CLI
templates/             interface Jinja2 responsiva
static/                CSS e JavaScript
migrations/            histórico versionado do esquema
tests/                 regressões de regras críticas
```

## Segurança operacional

- senhas armazenadas por hash Werkzeug;
- CSRF obrigatório em métodos mutáveis;
- cookies HttpOnly/SameSite e Secure em produção;
- CSP e headers defensivos;
- autorização validada no backend com resposta 403;
- limite de tamanho de requisição e página integrada de erros;
- `debug` desativado em produção.

## Roadmap

Próximas entregas: reserva transacional/MRP, lotes e rastreabilidade, centros de trabalho/roteiros/CRP, paginação completa, API v1 e, após estabilização, PWA e documentação Capacitor.

## Licença

MIT. Consulte [LICENSE](LICENSE).
