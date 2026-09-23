# RPA Consórcios BCB → WhatsApp

Automação full stack que **navega pelo Portal de Dados Abertos do Banco Central**, consulta o
*Panorama do Sistema de Consórcios*, **extrai e trata** os indicadores, **gera uma mensagem
personalizada** e a **envia por WhatsApp**, registrando todo o histórico. Um **dashboard**
com gráficos mostra a evolução do mercado, e o **progresso do robô aparece ao vivo** na tela.

```
Nova consulta → Executar RPA (progresso ao vivo) → Visualizar dados → Gerar mensagem → Enviar WhatsApp → Histórico
                                                                                        Dashboard ↗
```

---

## Sumário

1. [Arquitetura](#arquitetura)
2. [Tecnologias e justificativas](#tecnologias-e-justificativas)
3. [Instalação](#instalação)
4. [Execução](#execução)
5. [Configurando o WhatsApp](#configurando-o-whatsapp)
6. [Como o RPA funciona](#como-o-rpa-funciona)
7. [Progresso do robô em tempo real](#progresso-do-robô-em-tempo-real)
8. [Tratamento e validação dos dados](#tratamento-e-validação-dos-dados)
9. [Dashboard](#dashboard)
10. [Tratamento de erros](#tratamento-de-erros)
11. [Controle de duplicidade](#controle-de-duplicidade)
12. [Histórico e logs](#histórico-e-logs)
13. [API](#api)
14. [Testes](#testes)
15. [Estrutura de pastas](#estrutura-de-pastas)
16. [Dificuldades encontradas](#dificuldades-encontradas)
17. [O que mudaria para produção](#o-que-mudaria-para-produção)

---

## Arquitetura

```
┌──────────────────────┐   HTTP/JSON   ┌────────────────────────────────────────────────────────┐
│  Frontend (React)    │ ────────────► │  Backend (FastAPI)                                     │
│  - Nova consulta     │  POST + poll  │                                                        │
│    + progresso ao    │ ◄──────────── │  api.py ──► services/consultas.py (orquestração)       │
│      vivo do robô    │   etapas      │               │  duplicidade + retry + 2º plano        │
│  - Dados encontrados │               │               ▼                                        │
│  - Mensagem / envio  │               │  rpa/bcb_portal.py ──(Playwright/Chromium)──┐          │
│  - Dashboard         │               │     │ reportar(etapa)                       ▼          │
│  - Histórico         │               │     ▼                             Portal de Dados      │
└──────────────────────┘               │  progresso.py (canal de progresso)  Abertos → Olinda   │
                                       │  rpa/olinda_api.py  (plano B, HTTP direto)             │
                                       │  services/tratamento.py   services/mensagem.py         │
                                       │  services/serie.py ──► services/dashboard.py           │
                                       │  services/envios.py ──► whatsapp/providers.py ──► link wa.me / Meta / Twilio
                                       │               │                                        │
                                       │               ▼                                        │
                                       │  SQLite (execucoes, mensagens, serie_metricas)         │
                                       │  + logs/rpa.log                                        │
                                       └────────────────────────────────────────────────────────┘
```

**Separação de responsabilidades**

| Camada | Arquivo(s) | Responsabilidade |
|---|---|---|
| HTTP | `app/api.py`, `app/main.py` | Traduz HTTP ↔ serviços; mapeia erros de domínio para status HTTP |
| Orquestração | `app/services/consultas.py` | Validação, trava de duplicidade, retentativas, plano B, execução em segundo plano, persistência |
| Automação | `app/rpa/bcb_portal.py` | Navegação no portal com Playwright |
| Progresso | `app/progresso.py` | Canal que leva cada etapa do robô até a execução (e dali para a tela) |
| Tratamento | `app/services/tratamento.py` | Validação, correção de unidades, normalização, estruturação |
| Mensagem | `app/services/mensagem.py` | Gera o texto a partir dos dados estruturados |
| Envio | `app/services/envios.py`, `app/whatsapp/providers.py` | Idempotência do envio; integração com o provedor |
| Dashboard | `app/services/serie.py`, `app/services/dashboard.py` | Série histórica por trimestre e agregação para os gráficos |
| Persistência | `app/models.py`, `app/database.py` | Modelos, sessão do banco e migração automática de colunas novas |
| Configuração | `app/config.py` + `.env` | Tudo que é sensível ou muda por ambiente |

---

## Tecnologias e justificativas

| Tecnologia | Por quê |
|---|---|
| **Python 3.12+** | Ecossistema forte para RPA e tratamento de dados. |
| **Playwright** | Espera automática por elementos, captura da **resposta de rede** da página, modo headless/visível e screenshots de falha. Mais estável que Selenium em páginas dinâmicas (o portal é Angular). |
| **FastAPI** | API tipada com validação automática (Pydantic) e documentação interativa em `/docs`. |
| **SQLAlchemy + SQLite** | Não precisa de servidor para a demonstração. Os **índices únicos parciais** garantem no próprio banco que não haja processamento nem envio duplicado. Para migrar para PostgreSQL, basta trocar a `DATABASE_URL`. |
| **tenacity** | Retentativa com *backoff* exponencial só para erros transitórios. |
| **httpx** | Cliente HTTP para o plano B e para as APIs de WhatsApp. |
| **React + Vite + TypeScript** | Interface simples com tipos espelhando a API. O build é servido pelo próprio FastAPI, então a demonstração sobe com um comando só. |
| **Recharts** | Gráficos declarativos em React, com tooltip e legenda prontos. É carregado **só quando a aba Dashboard é aberta** (*lazy loading*), para a tela inicial continuar leve. |
| **WhatsApp: link oficial wa.me (padrão) + Cloud API da Meta** | O `wa.me` abre o WhatsApp de quem usa o sistema com a conversa e a mensagem prontas: não exige conta, token nem aprovação, respeita os termos de uso e quem confirma o envio é o próprio usuário. Para envio 100% automático, a integração com a Cloud API oficial da Meta já está pronta (`WHATSAPP_PROVIDER=meta`). A Twilio e o `mock` também estão disponíveis. Ver [justificativa](#justificativa-da-estratégia). |

---

## Instalação

Pré-requisitos: **Python 3.12+** e **Node.js 20+**.

> No **VS Code**: abra a pasta do projeto (a que contém `backend`, `frontend` e este README),
> depois *Terminal → Novo Terminal* e rode os comandos abaixo, **um por vez**.
> Os comandos usam `.venv\Scripts\python` direto, sem "ativar" o ambiente, porque o PowerShell
> costuma bloquear o script de ativação.

```bash
# 1) Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
copy .env.example .env

# 2) Frontend
cd ..\frontend
npm install
npm run build
```

> Linux/macOS: troque `.venv\Scripts\python` por `.venv/bin/python` e `copy` por `cp`.

---

## Execução

### Opção A — um comando (demonstração)

Com o frontend já compilado (`npm run build`), dentro de `backend`:

```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Acesse **http://localhost:8000**. A documentação da API fica em **http://localhost:8000/docs**.

### Opção B — desenvolvimento (hot reload no front)

```bash
# terminal 1 (dentro de backend)
.venv\Scripts\python -m uvicorn app.main:app --port 8000

# terminal 2 (dentro de frontend)
npm run dev
```
Acesse **http://localhost:5173**. O Vite redireciona as chamadas `/api` para o backend.

> **Dica para a apresentação:** use `RPA_HEADLESS=false` no `.env` para o navegador abrir
> na tela e todos verem o robô preenchendo o formulário do BCB — enquanto a interface mostra
> cada etapa ao vivo.

**Primeiro uso do dashboard:** abra a aba **Dashboard** e clique em **Carregar histórico**. O robô
busca os últimos trimestres no portal (≈ 25 s para 12 trimestres) e os gráficos aparecem.

---

## Configurando o WhatsApp

O provedor é escolhido por `WHATSAPP_PROVIDER` no `.env`. Nenhuma credencial fica no código.

| Valor | Como envia | Precisa de conta? |
|---|---|---|
| `link` (padrão) | Abre o WhatsApp de quem usa o sistema com a mensagem pronta; a pessoa toca em Enviar | Não |
| `meta` | Envio 100% automático pela Cloud API oficial | Sim (app na Meta) |
| `twilio` | Envio automático pelo sandbox da Twilio | Sim (conta Twilio) |
| `mock` | Não envia; só registra no log (desenvolvimento) | Não |

### Link wa.me (padrão, sem configuração)

`WHATSAPP_PROVIDER=link`. Ao clicar em **Enviar WhatsApp**, o sistema registra o envio e abre
uma aba com o link oficial `https://wa.me/<número>?text=<mensagem>`. O WhatsApp (app ou Web)
de quem está usando o sistema abre com a conversa e a mensagem prontas, e basta tocar em **Enviar**.
Se o navegador bloquear a aba, o botão verde **"Abrir no WhatsApp novamente"** abre o mesmo link.

**Troca consciente:** o último clique é humano, então o sistema registra que a mensagem foi
*aberta no WhatsApp*, mas não recebe confirmação de entrega. Para envio totalmente automático
com ID de entrega, use a Cloud API da Meta.

### Meta WhatsApp Cloud API (envio automático)

1. Acesse <https://developers.facebook.com> → **Criar app** → tipo *Business* → adicione o produto **WhatsApp**.
2. Em **WhatsApp → API Setup**:
   - copie o **Temporary access token** → `META_ACCESS_TOKEN`
   - copie o **Phone number ID** → `META_PHONE_NUMBER_ID`
   - em **To**, adicione e verifique o seu número de demonstração (máx. 5 números no modo de teste).
3. **Importante (janela de 24h):** a Meta só permite enviar texto livre se o destinatário
   mandou uma mensagem ao número do negócio nas últimas 24h. Antes da demonstração, **envie
   um "oi" do seu celular para o número de teste**. Sem isso, a API retorna o erro `131047`,
   que o sistema registra no histórico com a explicação.
4. `WHATSAPP_PROVIDER=meta` e reinicie o backend.

#### Teste antes da apresentação

Há um comando que testa as credenciais sem precisar abrir a interface (rode dentro de `backend/`):

```bash
# 1) Valida token, Phone Number ID e número autorizado (template hello_world, funciona sem janela de 24h)
.venv\Scripts\python -m app.whatsapp.testar 11999998888 --template

# 2) Responda qualquer coisa a essa mensagem no seu WhatsApp (abre a janela de 24h)

# 3) Confirma que texto livre chega (é o tipo de mensagem que o sistema envia)
.venv\Scripts\python -m app.whatsapp.testar 11999998888
```

Se o passo 1 falhar, o problema está nas credenciais ou no número autorizado. Se só o passo 3 falhar
com o código `131047`, falta abrir a janela de 24h.

> O token temporário expira em 24h. Para uso contínuo, gere um token de *System User* no Business Manager.

### Twilio (alternativa)

1. Crie uma conta em <https://www.twilio.com> → **Messaging → Try it out → Send a WhatsApp message**.
2. Do seu celular, envie `join <código>` para o número do sandbox (+1 415 523 8886).
3. Preencha `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886`.
4. `WHATSAPP_PROVIDER=twilio`.

### Justificativa da estratégia

- **Demonstração → link `wa.me`:** é o recurso oficial de *click-to-chat* do WhatsApp. Funciona
  em qualquer máquina sem cadastro, token ou aprovação de modelo, e não viola os termos de uso,
  porque quem envia é o próprio usuário, pela conta dele.
- **Produção → Cloud API da Meta:** envio sem intervenção humana, ID de cada mensagem para
  rastreio e webhooks de entrega/leitura. Já está implementada e testada.
- **Descartado → automatizar o WhatsApp Web** (whatsapp-web.js, Baileys): é rápido de montar,
  mas **viola os Termos de Uso** (o número pode ser banido), quebra quando o WhatsApp muda o
  front e exige manter uma sessão com QR Code.

Como todos os provedores seguem a mesma interface (`enviar(numero, texto)`), trocar de um
para outro é só mudar uma variável no `.env`.

---

## Como o RPA funciona

Fonte: **Portal Olinda do BCB** — *Panorama do Sistema de Consórcios*
(<https://olinda.bcb.gov.br/olinda/servico/PANORAMA_DE_CONSORCIOS/versao/v1/aplicacao#!/recursos/Metricas>),
listado no Portal de Dados Abertos como *Dados Agregados do Segmento de Consórcios*.

Passo a passo (`app/rpa/bcb_portal.py`):

**Navegação até a área de consulta**

1. Abre o Chromium na página inicial do **Portal de Dados Abertos** (<https://dadosabertos.bcb.gov.br>).
2. Pesquisa **"consórcios"** na busca do portal.
3. Nos resultados, abre o conjunto **"Dados Agregados do Segmento de Consórcios"**.
4. Abre o recurso **"Métricas"** e confere que o link **"Ir para recurso"** aponta para o serviço certo.
5. Clica em **"Ir para recurso"** e chega ao formulário de consulta do portal Olinda.

**Consulta**

6. Espera o Angular montar o formulário (campo **Data Base**).
7. Preenche **Data Base** (ex.: `202606`), **Máximo** (`1000`) e **Saída** (`json`).
8. Confere que a **URL de pesquisa** gerada pelo portal contém o parâmetro digitado.
9. Clica em **Executar** e **aguarda a resposta** da consulta.
10. Lê os registros dessa resposta e **valida pelo DOM** que a grade apareceu com as colunas esperadas.
11. Repete para o **trimestre anterior** na mesma sessão, para calcular as variações.

> **Resiliência na navegação:** se alguma etapa do catálogo (1–5) falhar, por exemplo por mudança
> de layout, o robô salva um screenshot, registra um aviso no log e segue pelo **link direto do
> formulário**. Essas etapas não afetam os dados, então não faz sentido parar a operação por
> causa delas. Para pular o catálogo, deixe `BCB_DADOS_ABERTOS_URL=` vazio no `.env`.

### Estratégia de extração

A grade de resultados do portal (Angular *ui-grid*) é **virtualizada**: só as ~15 linhas
visíveis existem no HTML. Raspar o DOM exigiria rolar a grade e remontar as linhas, o que é lento e frágil.
Por isso, o robô **escuta a resposta de rede que a própria página recebe ao clicar em
Executar** (`page.expect_response`), que é o mesmo JSON que alimenta a grade. Resultado:

- dados completos e tipados (números como números, não texto formatado);
- sem depender de CSS/posição das colunas;
- o DOM continua sendo usado para **validar** que a navegação deu certo.

Os seletores ficam centralizados no topo do arquivo. Se o portal mudar, só esse bloco precisa de ajuste.

---

## Progresso do robô em tempo real

Uma consulta leva de 5 a 35 s (o portal do BCB às vezes demora mais de 10 s só para abrir). Em vez
de um spinner parado, a tela mostra cada etapa do robô **enquanto ela acontece**:

```
⟳ Robô em execução                                                  12,4 s
✓ Consulta registrada; aguardando o robô                            +0,0 s
✓ Iniciando o robô (tentativa 1 de 3)                               +0,0 s
✓ Abrindo o Portal de Dados Abertos do Banco Central                +2,3 s
✓ Pesquisando “consórcios”                                          +8,0 s
✓ Abrindo o conjunto “Dados Agregados do Segmento de Consórcios”    +9,2 s
⟳ Abrindo o recurso “Métricas”                                     +10,6 s
```

**Como funciona**

1. O frontend envia `POST /api/consultas` com `em_segundo_plano: true`. O backend valida, aplica as
   travas de duplicidade, cria a execução `EM_EXECUCAO` e **responde na hora**.
2. O robô roda em segundo plano (`BackgroundTasks` do FastAPI), numa sessão de banco própria.
3. A cada passo, o robô chama `reportar("…")` (`app/progresso.py`). O orquestrador registra um
   *ouvinte* que grava a etapa em `execucoes.etapas`, com horário.
4. O frontend consulta `GET /api/consultas/{id}` a cada 0,8 s (*polling*) e desenha a linha do tempo
   até o status mudar.

**Decisões**

- **Robô desacoplado da tela:** ele só "anuncia" as etapas; não sabe quem ouve. O canal usa
  `ContextVar`, então duas consultas em paralelo não misturam as etapas. Sem ouvinte (testes,
  carregamento de histórico), `reportar` não faz nada.
- **Falha no registro do progresso nunca derruba o robô.**
- **Retentativas e plano B também aparecem** ("Tentativa 1 falhou…", "consultando a API OData (plano B)").
- **As etapas ficam salvas:** depois de concluída, a execução mostra "Etapas executadas pelo robô",
  com o tempo de cada uma — o que serve também como rastreabilidade.
- **Polling em vez de WebSocket:** mais simples, sem conexão aberta e fácil de depurar. Para
  muitos usuários simultâneos, SSE/WebSocket seria o próximo passo (ver produção).
- O modo síncrono continua disponível (`em_segundo_plano: false`, o padrão da API).

---

## Tratamento e validação dos dados

`app/services/tratamento.py` transforma ~125 linhas (uma por métrica) em informação estruturada:

1. **Validação:** descarta registros sem `IdMetrica` ou sem valor numérico, detecta duplicados e gera um aviso para cada caso.
2. **Correção de unidades:** confere se o **total é igual à soma das partes**. Os dados reais do BCB têm dois erros:
   - métrica 37 (contempladas – motocicletas) vem como `mi`, mas é `mil`;
   - métrica 68 (recursos a coletar – total) vem como `R$ milhões`, mas o valor é exatamente
     a soma das partes em `R$ bilhões`.

   Nesses casos, o sistema corrige a unidade e **registra um aviso** visível na tela e no histórico.
3. **Normalização:** `mil`, `R$ bilhões` etc. viram valores absolutos.
4. **Seleção:** monta os indicadores do segmento escolhido. Os que a fonte não publica para
   aquele segmento (ex.: carteira de veículos pesados) são omitidos, sem quebrar a execução.
5. **Comparação:** calcula a variação contra o trimestre anterior (% para quantidades, **p.p.** para
   percentuais). Se o trimestre anterior não existir, gera um aviso e não mostra variação.
6. **UF:** cotas ativas, participação no país e posição no ranking.

---

## Dashboard

Aba **Dashboard**, com filtros de **segmento**, **UF em destaque** e **trimestre de referência**:

| Elemento | O que mostra |
|---|---|
| **Cartões (KPIs)** | Cotas ativas, carteira, cotas vendidas, inadimplência e cotas da UF, com variação contra o trimestre anterior e um minigráfico dos últimos 8 trimestres |
| **Linhas** | Evolução das cotas ativas e da carteira do segmento; inadimplência × pré-inadimplência |
| **Rosca** | Composição do mercado por segmento, com o total no centro e o % de cada fatia |
| **Barras empilhadas** | Contemplações por sorteio × lance em cada segmento |
| **Barras horizontais** | Ranking das 27 UFs em cotas ativas, com a UF escolhida em destaque |

**De onde vêm os dados:** a tabela `serie_metricas` guarda um valor por *(trimestre, métrica)*, já
validado, com unidade corrigida e normalizado. Ela é alimentada de dois jeitos:

- **toda consulta** feita em "Nova consulta" grava o trimestre consultado e o anterior;
- o botão **Carregar histórico** manda o robô buscar vários trimestres (8 a 40) **numa única sessão
  do navegador**, pulando os que já estão na base e guardando exatamente a quantidade pedida.
  Só um carregamento roda por vez (trava contra duplicidade).

**Decisões de visualização**

- **Um eixo por gráfico** (nunca dois eixos Y), linhas finas e poucas cores.
- **Paleta validada** para daltonismo e contraste, nos modos claro e escuro.
- **A cor segue o segmento, não o ranking:** Imóveis tem sempre a mesma cor e a mesma posição na
  rosca, mesmo quando troca de lugar com Motocicletas de um trimestre para outro.
- A rosca tem **no máximo 5 fatias**: "Outros bens" e "Serviços", finas demais sozinhas, viram uma.
- **Cores com significado:** em inadimplência, taxa de administração e índice de exclusão, **subir é
  vermelho** e cair é verde (o contrário dos demais indicadores).
- **Tabela de dados em todo gráfico** ("Ver dados em tabela"), para quem não distingue cores ou
  prefere números.

---

## Tratamento de erros

| Situação | Como é tratada | Status registrado |
|---|---|---|
| **Consulta sem resultado** (ex.: `202605`, mês não publicado) | Resposta vazia é detectada e a mensagem explica a periodicidade trimestral | `SEM_RESULTADO` |
| **Informações incompletas** | Métrica sem valor ou ausente → aviso e o indicador é omitido | `SUCESSO` + avisos |
| **Indisponibilidade temporária** (timeout, HTTP 5xx, erro do Olinda) | `FonteIndisponivel` → **até 3 tentativas com backoff exponencial**; se todas falharem, **plano B** via API OData | `SUCESSO` (fonte `api_fallback`) ou `ERRO` |
| **Falha de navegação no catálogo** (busca/conjunto/recurso não encontrado) | Screenshot + aviso no log; segue pelo link direto do formulário | `SUCESSO` (se o restante funcionar) |
| **Falha de navegação no formulário** (formulário não carregou, grade não apareceu, layout mudou) | `FalhaNavegacao` → retentativa + **screenshot** em `logs/screenshots/` | `ERRO` com descrição |
| **Resposta em formato inesperado** | `RespostaInvalida` (não adianta tentar de novo) | `ERRO` |
| **Processamento duplicado** | Ver [controle de duplicidade](#controle-de-duplicidade) | HTTP 409 |
| **Falha no envio do WhatsApp** | Erro do provedor é registrado com dica (ex.: janela de 24h); permite nova tentativa | `ERRO` na mensagem |
| **Erro inesperado** | Capturado e registrado; a execução nunca fica presa em `EM_EXECUCAO` | `ERRO` |
| **Aplicação derrubada no meio** | Na subida, execuções órfãs `EM_EXECUCAO` são marcadas como erro | `ERRO` |
| **Banco criado por uma versão anterior** | Na subida, colunas novas (ex.: `etapas`) são criadas automaticamente com `ALTER TABLE` | — |

---

## Controle de duplicidade

**Processamento**

- Cada consulta tem uma chave `AAAAMM|SEGMENTO|UF`.
- **Índice único parcial** no banco: só pode haver **uma** execução `EM_EXECUCAO` por chave.
  Se duas requisições chegarem juntas (duplo clique, duas abas), a segunda recebe **HTTP 409**.
  A garantia está no banco, então não depende de *lock* em memória.
- Dados de uma data-base passada não mudam: uma consulta idêntica já concluída é
  **reaproveitada** sem rodar o robô de novo. Para forçar, marque "Reprocessar".
- Enquanto o robô roda, o botão fica travado ("Robô em execução…"), evitando clique duplo.
- O **Carregar histórico** do dashboard só roda um por vez (HTTP 409 para o segundo).

**Envio**

- Cada mensagem tem `chave_idempotencia = sha256(número + texto)`.
- Antes de chamar o provedor, a mensagem é **reservada** (`ENVIANDO`) numa transação.
  Um índice único parcial impede duas linhas `ENVIANDO/ENVIADA` com a mesma chave.
- Reenviar uma mensagem já enviada → **HTTP 409** (`ENVIO_DUPLICADO`).
- "Gerar mensagem" repetido com os mesmos dados devolve a mesma mensagem, sem criar outra.
- Mensagens com `ERRO` podem ser reenviadas.

---

## Histórico e logs

Tela **Histórico** (e `GET /api/historico`). Cada execução registra:

| Requisito | Onde |
|---|---|
| Consulta realizada | `data_base`, `segmento`, `uf` |
| Informações encontradas | `dados` (tratados) + `registros_brutos` (exatamente como vieram do BCB, em `/api/consultas/{id}/bruto`) |
| Data e hora | `iniciado_em`, `finalizado_em`, `criado_em`, `enviado_em` |
| Destinatário | `destinatario_nome`, `destinatario_numero` |
| Mensagem gerada | `texto` |
| Status do processamento e do envio | `execucoes.status`, `mensagens.status`, `fonte`, `tentativas`, `provedor_message_id` |
| Descrição do erro | `execucoes.erro`, `mensagens.erro`, `avisos` |
| Passo a passo do robô | `execucoes.etapas` (texto + horário de cada etapa) |

**Logs:** `backend/logs/rpa.log` (rotativo, 5 MB × 5) + console. Os números de telefone
aparecem **mascarados** nos logs.

---

## API

Documentação interativa em `/docs`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/opcoes` | Segmentos, UFs e data-bases sugeridas |
| POST | `/api/consultas` | Executa o RPA `{data_base, segmento, uf?, forcar?, em_segundo_plano?}`. Com `em_segundo_plano: true`, responde na hora com `EM_EXECUCAO` |
| GET | `/api/consultas/{id}` | Uma execução, com as `etapas` (usado para acompanhar o progresso) |
| GET | `/api/consultas/{id}/bruto` | Registros brutos da fonte |
| POST | `/api/mensagens` | Gera mensagem `{execucao_id, destinatario_nome, destinatario_numero}` |
| POST | `/api/mensagens/{id}/enviar` | Envia via WhatsApp (no modo `link`, devolve o link wa.me) |
| GET | `/api/historico` | Execuções com suas mensagens |
| GET | `/api/dashboard?segmento=&uf=&data_base=` | Dados agregados para os gráficos |
| POST | `/api/dashboard/historico` | Robô busca vários trimestres `{trimestres: 4..40}` |

---

## Testes

Dentro de `backend`:

```bash
.venv\Scripts\python -m pytest -q
```

São 56 testes que rodam **sem internet**, usando dados reais do BCB gravados em
`tests/fixtures/`. Eles cobrem: tratamento (correção de unidades, dados incompletos, UF ausente),
formatação da mensagem, retentativa e plano B, consulta sem resultado, erro inesperado,
travas de duplicidade (processamento e envio), validação de entrada, integração com a Meta
(com `respx`), o fluxo completo pela API, **série histórica e dashboard** (inclusive "carregar só
o que falta") e **progresso em tempo real** (etapas gravadas, retentativas visíveis, modo em
segundo plano e migração de banco antigo).

---

## Estrutura de pastas

```
backend/
  app/
    main.py              # app FastAPI, logs, handlers de erro, serve o frontend
    api.py               # rotas
    config.py            # configurações (.env)
    database.py          # sessão do banco + migração automática de colunas novas
    models.py schemas.py exceptions.py
    progresso.py         # canal de progresso do robô (etapas ao vivo)
    rpa/
      bcb_portal.py      # robô Playwright
      olinda_api.py      # plano B (HTTP direto)
    services/
      consultas.py       # orquestração do RPA
      tratamento.py      # extração → dados estruturados
      mensagem.py        # geração do texto
      envios.py          # geração/envio com idempotência
      serie.py           # grava a série histórica por trimestre
      dashboard.py       # carregar histórico + dados dos gráficos
    whatsapp/
      providers.py       # Link wa.me, Meta, Twilio, Mock
      testar.py          # python -m app.whatsapp.testar <numero>
  tests/
  requirements.txt  .env.example
frontend/
  src/
    App.tsx  api.ts  formato.ts  styles.css
    components/ ConsultaForm, ProgressoRobo, Resultado, MensagemPainel,
                Dashboard, Graficos, Historico, StatusBadge
```

---

## Dificuldades encontradas

- **Grade virtualizada:** a raspagem do DOM só enxergava ~15 das 125 linhas. A solução foi capturar
  a resposta de rede da página e usar o DOM apenas para validação.
- **Inconsistências na própria fonte:** unidades erradas (`mi`, `R$ milhões`) em duas métricas,
  descobertas comparando total × soma das partes. Por isso a checagem virou uma regra genérica.
- **Periodicidade:** o panorama é trimestral e com defasagem, então meses "normais" retornam vazio.
  Isso virou o caso "sem resultado", e a interface sugere só meses de fim de trimestre.
- **Erros do Olinda:** o serviço devolve erro como JSON dentro de comentário (`/*{...}*/`) com
  HTTP 200 em alguns casos, o que exigiu tratamento específico.
- **Janela de 24h da Meta:** a mensagem de texto livre só é entregue se o destinatário tiver falado com
  o número antes. Por isso a mensagem de erro já traz a orientação, e o modo `link` virou o padrão
  para a demonstração.
- **Bloqueio de pop-up:** abrir o WhatsApp depois da resposta do servidor era bloqueado pelo
  navegador. A solução foi abrir a aba no próprio clique e só depois preencher o endereço.
- **Console do Windows:** o terminal (cp1252) não exibia emojis e setas dos logs e gerava
  "Logging error". O console passou a substituir caracteres não suportados; o arquivo de log
  continua em UTF-8.
- **Espera longa sem retorno:** o portal do BCB chega a levar mais de 10 s só para abrir, e um
  spinner parado parecia travamento. A solução foi rodar o robô em segundo plano e mostrar cada
  etapa ao vivo.
- **Banco já existente ao adicionar colunas:** `create_all` não altera tabelas. Uma migração
  simples na subida cria as colunas que faltam, sem perder dados.
- **Cores dos gráficos legíveis para todos:** em vez de escolher cores "no olho", a paleta foi
  validada por script (contraste com o fundo e separação para os tipos de daltonismo), nos modos
  claro e escuro, antes de ser usada.

---

## O que mudaria para produção

- **Fila de jobs** (Celery/RQ + Redis ou SQS) no lugar do `BackgroundTasks`: o robô rodaria em
  *workers* separados da API, sobreviveria a reinícios e escalaria horizontalmente.
- **SSE ou WebSocket** no lugar do polling, empurrando cada etapa para a tela assim que acontece.
- **Agendamento:** execução automática quando o BCB publica um novo trimestre.
- **PostgreSQL + Alembic** (migrações versionadas) no lugar de SQLite + `create_all` e da
  migração manual de colunas.
- **WhatsApp com templates aprovados** pela Meta (necessário para iniciar conversas fora da
  janela de 24h), token de *System User* e **webhook de status** (entregue/lida/falhou).
- **Segredos** em cofre (Azure Key Vault, AWS Secrets Manager), não em `.env`.
- **Autenticação/autorização** na interface e na API; auditoria por usuário; LGPD
  (consentimento e opt-out dos destinatários, retenção dos dados).
- **Observabilidade:** logs estruturados em JSON, métricas (tempo de execução, taxa de falha)
  e alertas; *tracing*.
- **Containers** (Docker com a imagem oficial do Playwright), CI/CD rodando testes e lint.
- **Monitoramento da fonte:** um teste diário contra o portal real que alerta se o layout mudar.
- **Rate limit e circuit breaker** nas chamadas externas.