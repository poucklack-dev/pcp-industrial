# Auditoria técnica inicial

Data: 2026-09-02

## Topologia encontrada

- `app.py`: criação da aplicação e registro de oito blueprints.
- `backend/models.py`: 10 modelos em arquivo único (ainda administrável; separação adiada para evitar uma migração estrutural arriscada).
- `backend/services.py`: explosão, verificação e consumo de BOM, entrada de produção.
- `templates/`: nove telas Jinja; produtos, ordens e estoque são os maiores candidatos à componentização progressiva.
- `static/`: CSS e JavaScript globais.
- banco SQLite legado em `instance/pcp.db`.

## Rotas mapeadas

- autenticação: login, logout, recuperação e gestão de usuários;
- dashboard: `/`;
- produtos/BOM: listagem, CRUD, detalhe JSON e componentes;
- ordens: listagem, criação, detalhe, apontamento, estado, reabertura e exclusão;
- apontamentos: listagem e inclusão;
- estoque: painel, ajuste e configuração;
- cadastros: máquinas;
- relatórios: painel e consultas JSON de produção, consumo, OP, apontamento, estoque e histórico;
- infraestrutura adicionada: `GET /health`.

O mapa executável completo pode ser obtido com `flask --app app routes`.

## Modelos e relações

- `Usuario` 1–0..1 `Operador`;
- `Maquina` 1–N `Produto`;
- `Produto` N–N autorreferente por `Estrutura` (`produto_pai`/`componente`);
- `Produto` 1–N `OrdemProducao`;
- `OrdemProducao` 1–N `Apontamento`, `Movimentacao` e `Historico`;
- `Operador` 1–N `Apontamento`;
- `Apontamento` 1–N `Movimentacao`;
- `Configuracao`: política global de estoque negativo.

## Regras observadas

- PA aceita MP/SA e SA aceita MP; circularidade é bloqueada no cadastro.
- apontamento exige `produzida = boa + refugo`, respeita o limite planejado, consome componentes e registra entrada da quantidade boa.
- toda alteração de saldo existente passa por `Movimentacao`; estoque negativo é bloqueado conforme configuração.
- permissões são verificadas nas rotas pelo decorator `permissao_requerida`.

## Riscos encontrados e tratamento

- **Crítico, corrigido:** segredo e banco configurados dentro da aplicação; agora há configuração por ambiente e segredo obrigatório em produção.
- **Crítico, corrigido:** `db.create_all`, alterações DDL e usuário com senha fixa no startup; substituídos por migration e seed explícitos.
- **Alto, corrigido:** ausência de CSRF e logout por GET; métodos mutáveis agora exigem token e logout usa POST.
- **Alto, corrigido:** autorização negada redirecionava; agora retorna 403 no backend.
- **Alto, corrigido:** explosão exibida ignorava intermediários/perdas; agora é multinível, acumulativa e detecta ciclos defensivamente.
- **Alto, corrigido:** estados de OP aceitavam saltos arbitrários; transições possuem mapa explícito.
- **Alto, pendente:** ainda não existe reserva de estoque concorrente; liberar OP deve ganhar transação e registros de reserva antes de uso empresarial.
- **Alto, pendente:** consumo atual é da BOM direta; a política fabricar-versus-consumir SA precisa ser formalizada junto ao MRP.
- **Médio, pendente:** movimentação não armazena saldo anterior/posterior nem FK de usuário.
- **Médio, pendente:** ausência de lotes, auditoria global, roteiro, centro de trabalho e capacidade.
- **Médio, pendente:** listagens principais ainda usam `.all()` e precisam de paginação server-side.
- **Médio, pendente:** mensagens de exceção ainda chegam ao usuário em algumas rotas; devem ser substituídas por códigos e logs controlados.

## Sequência recomendada

1. Reserva/MRP e razão de estoque transacional, com migrations e testes de concorrência lógica.
2. Auditoria, lotes e rastreabilidade.
3. Centro de trabalho, roteiro e capacidade.
4. Paginação, filtros e exportações.
5. API v1; depois PWA, scanner e documentação Capacitor.
