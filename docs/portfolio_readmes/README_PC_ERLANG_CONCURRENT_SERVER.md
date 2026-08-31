# ⚡ Servidor de Jogo Concorrente Distribuído em Erlang

<p align="center">
  <img src="https://img.shields.io/badge/Linguagem-Erlang%2FOTP-A90533?style=for-the-badge&logo=erlang&logoColor=white" alt="Erlang/OTP" />
  <img src="https://img.shields.io/badge/Concorr%C3%AAncia-Modelo_de_Atores-008080?style=for-the-badge" alt="Modelo de Atores" />
  <img src="https://img.shields.io/badge/Rede-Sockets_gen__tcp-darkblue?style=for-the-badge" alt="gen_tcp" />
  <img src="https://img.shields.io/badge/Cliente-Processing_%28Java%29-0468FF?style=for-the-badge&logo=processing&logoColor=white" alt="Processing" />
  <img src="https://img.shields.io/badge/Unidade_Curricular-Programa%C3%A7%C3%A3o_Concorrente-purple?style=for-the-badge" alt="Programação Concorrente" />
</p>

> Servidor de jogo multijogador tolerante a falhas e de alta concorrência desenvolvido segundo o Modelo de Atores em Erlang/OTP, com comunicação por sockets TCP assíncronos, processos independentes para emparelhamento de jogadores e simulação de partidas, e persistência binária em disco.

---

## 🎯 Contextualização e Objetivo

A implementação de servidores de jogos em tempo real com arquiteturas clássicas baseadas em threads e bloqueios (*mutexes*) enfrenta sérios riscos de sincronização: deadlocks, condições de corrida e contenção de recursos.

Este projeto adota o **Modelo de Atores do Erlang/OTP** (*share-nothing architecture*), onde cada cliente conectado, sala de espera e partida ativa é executado como um processo leve e isolado da máquina virtual BEAM, comunicando exclusivamente por troca assíncrona de mensagens.

---

## 🏛️ Arquitetura de Atores e Fluxo de Mensagens

```
                      ┌───────────────────────────┐
                      │    Cliente Processing     │
                      └─────────────┬─────────────┘
                                    │ Socket TCP Porta 12345 (Pacotes por Linha)
                                    ▼
                      ┌───────────────────────────┐
                      │      server.erl (TCP)     │ (gen_tcp:listen & despachador)
                      └──────┬─────────────┬──────┘
                             │             │
             Autenticação    │             │ Nova Ligação
                             ▼             ▼
        ┌──────────────────────────┐ ┌──────────────────────────┐
        │       accounts.erl       │ │        lobby.erl         │
        │ (Estado de utilizadores) │ │   (Fila de Matchmaking)  │
        └────────────┬─────────────┘ └─────────────┬────────────┘
                     │                             │ Emparelha Jogadores
                     │ Guarda/Carrega Binário      ▼
                     ▼               ┌──────────────────────────┐
        ┌──────────────────────────┐ │       game_sim.erl       │
        │       offline.erl        │ │ (Simulação da Partida)   │
        │ (accounts.bin, levels.bin│ │ - Timer periódico de 1s  │
        └──────────────────────────┘ │ - Processamento de ações │
                                     └──────────────────────────┘
```

---

## 🔬 Atores Principais do Sistema

### 1. Aceitador de Ligações TCP (`server.erl`)
- Inicializa a escuta no porto 12345 com `gen_tcp:listen(Port, [binary, {packet, line}, {reuseaddr, true}])`.
- Cria um processo leitor dedicado para cada ligação de rede, impedindo que latências de um cliente bloqueiem o servidor.

### 2. Gestor de Contas e Sessões (`accounts.erl`)
- Mantém em memória o mapa de utilizadores autenticados, níveis e identificadores de processo (PIDs).
- Coordena a gravação assíncrona dos estados no disco.

### 3. Fila de Espera e Matchmaking (`lobby.erl`)
- Organiza a fila de espera de jogadores conectados (`WaitingPlayers`).
- Quando dois jogadores estão disponíveis, instancia imediatamente um novo processo `game_sim` para acolher a partida e liberta a fila.

### 4. Simulação de Jogo Isolada (`game_sim.erl`)
- Cada partida corre no seu próprio ator independente.
- Utiliza `timer:send_interval(1000, tick)` para gerar um relógio determinístico de atualização de estado a cada segundo.
- Se uma partida terminar ou falhar de forma anómala, o processo é encerrado sem afetar os restantes jogos nem o servidor principal.

### 5. Persistência Binária em Disco (`offline.erl`)
- Serializa termos Erlang em formato binário nativo (`term_to_binary/1` e `binary_to_term/1`), gravando os ficheiros `accounts.bin` e `levels.bin`.

---

## 🛠️ Tecnologias Utilizadas

- **Servidor**: Erlang/OTP (Erlang 24+)
- **Paradigma**: Modelo de Atores & Passagem Assíncrona de Mensagens
- **Comunicação**: Sockets TCP (`gen_tcp`)
- **Cliente Visual**: Processing (Java)

---

## 🚀 Como Compilar e Executar

### 1. Iniciar o Servidor Erlang
```bash
# Clonar o repositório
git clone https://github.com/joaofarys200/PC.git
cd PC/projeto/server

# Abrir o terminal interativo do Erlang
erl

# Compilar os módulos no terminal Erlang
1> c(server).
2> c(accounts).
3> c(lobby).
4> c(game_sim).
5> c(offline).

# Iniciar o servidor no porto 12345
6> server:start().
```

### 2. Iniciar o Cliente Gráfico
1. Abra o [Processing](https://processing.org/).
2. Carregue o projeto `projeto/Processing/main_/main_.pde`.
3. Inicie múltiplos clientes para testar o matchmaking e a concorrência em tempo real.

---

## 👥 Contexto Académico

Desenvolvido no âmbito da unidade curricular de **Programação Concorrente** na **Universidade do Minho**.
