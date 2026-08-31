# ☁️ Infraestrutura de Microsserviços & Autoscaler Dinâmico com Prometheus

<p align="center">
  <img src="https://img.shields.io/badge/Contentoriza%C3%A7%C3%A3o-Docker_%26_Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Reverse_Proxy-Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white" alt="Nginx" />
  <img src="https://img.shields.io/badge/Monitoriza%C3%A7%C3%A3o-Prometheus_%26_cAdvisor-E6522C?style=for-the-badge&logo=prometheus&logoColor=white" alt="Prometheus" />
  <img src="https://img.shields.io/badge/Backend-Python_Flask_%7C_OpenAPI-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Unidade_Curricular-Infraestruturas_Cloud-blue?style=for-the-badge" alt="ITI" />
</p>

> Infraestrutura completa de microsserviços em contentores Docker com balanceador de carga em Nginx (resolução dinâmica de DNS interno), telemetria em tempo real com cAdvisor e Prometheus, e um Autoscaler Horizontal em Python que dimensiona automaticamente réplicas da aplicação com base em métricas de carga e erros.

---

## 🎯 Contextualização e Objetivo

O dimensionamento estático de servidores em ambientes de produção resulta em desperdício de recursos em períodos de baixa atividade ou em degradação de serviço durante picos de tráfego.

Este projeto constrói uma infraestrutura cloud automatizada em malha fechada (*closed-loop*), onde métricas reais de utilização de CPU, taxa de pedidos por segundo e taxa de erros 5xx recolhidas pelo **Prometheus** orientam um **Autoscaler em Python** a instanciar ou terminar réplicas do backend em tempo real.

---

## 🏛️ Arquitetura da Infraestrutura

```
                    ┌────────────────────────┐
                    │    Tráfego de Clientes │
                    └───────────┬────────────┘
                                │ Porta 80
                                ▼
                    ┌────────────────────────┐
                    │      Nginx Proxy       │ (Resolução de DNS dinâmica no Docker
                    │  (Balanceador de Carga)│  com reavaliação a cada 5 segundos)
                    └───────────┬────────────┘
                                │
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
        ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
        │  API Flask  │  │  API Flask  │  │  API Flask  │  (Volume NFS Partilhado)
        │ (Réplica 1) │  │ (Réplica 2) │  │ (Réplica N) │
        └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
               │                │                │
               └────────────────┼────────────────┘
                                │ Exposição de Métricas (:5000/metrics)
                                ▼
┌─────────────┐         ┌─────────────┐
│  cAdvisor   ├────────►│ Prometheus  │◄─── Recolha periódica (scrape a cada 5s)
│ (Telemetria │         │ (Base Dados │
│ de Hardware)│         │  Temporal)  │
└─────────────┘         └──────┬──────┘
                               │ Consultas PromQL via HTTP
                               ▼
                    ┌────────────────────────┐
                    │ Autoscaler em Python   │ (Calcula CPU, pedidos/s e erros 5xx)
                    │  (Controlo Docker CLI) │──► `docker compose up --scale api=N`
                    └────────────────────────┘
```

---

## 🔬 Componentes da Solução

### 1. Balanceador de Carga Nginx com DNS Dinâmico (`nginx.conf`)
- Utiliza o servidor DNS interno do Docker (`127.0.0.11`) com TTL de 5 segundos (`resolver 127.0.0.11 valid=5s`).
- Diretiva `zone flask_backend 64k` combinada com `server api:5000 resolve` para descobrir novos contentores instanciados em runtime sem necessitar de reiniciar o processo do Nginx.

### 2. API Flask com Instrumentação de Métricas (`auth.py`)
- Instrumentada com a biblioteca oficial `prometheus_client`, expondo métricas customizadas de latência, contagem de pedidos e status HTTP no endpoint `/metrics`.
- Documentação interativa de endpoints OpenAPI gerada via Swagger (Flasgger).

### 3. Motor do Autoscaler Horizontal (`autoscaler.py`)
- Executa um loop de controlo periódico ($T = 10\text{s}$) consultando a API HTTP do Prometheus.
- Avalia simultaneamente:
  - **Uso de CPU Agregado**: $\sum(\text{rate}(\text{container\_cpu\_usage\_seconds\_total}[\Delta t]))$ recolhido pelo cAdvisor.
  - **Taxa de Pedidos (Throughput)**: $\text{rate}(\text{app\_requests\_total}[\Delta t])$.
  - **Pico de Erros de Servidor**: $\text{rate}(\text{app\_requests\_status\_total}\{status=~"5.."\}[\Delta t])$.
- Aplica histerese e períodos de arrefecimento (*cooldown*) para evitar oscilações destrutivas (*flapping*).
- Dispara comandos de escalonamento via `subprocess` chamando `docker compose up --scale api=N -d`.

---

## 🛠️ Tecnologias Utilizadas

- **Contentorização**: Docker & Docker Compose v2 (Especificação 3.9)
- **Ingresso & Proxy**: Nginx Alpine, DNS Bridge do Docker
- **Observabilidade**: Prometheus, Google cAdvisor, `prometheus_client`
- **Backend**: Python 3.11+, Flask, Flasgger (OpenAPI)

---

## 🚀 Como Executar

### 1. Iniciar os Serviços Base
```bash
# Clonar o repositório
git clone https://github.com/joaofarys200/ITIPOSAPRESENTACAO.git
cd ITIPOSAPRESENTACAO

# Iniciar a infraestrutura com 2 réplicas da API
docker compose up --scale api=2 -d
```

### 2. Aceder aos Painéis
- **Aplicação / Nginx**: [http://localhost:80](http://localhost:80)
- **Documentação Swagger da API**: [http://localhost:80/apidocs/](http://localhost:80/apidocs/)
- **Dashboard do Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Métricas do cAdvisor**: [http://localhost:8080](http://localhost:8080)

### 3. Iniciar o Autoscaler Autónomo
```bash
python autoscaler.py
```

### 4. Simular Carga de Tráfego
```bash
# Simular pedidos concorrentes com Apache Bench
ab -n 10000 -c 50 http://localhost/
```
Observe nos logs do autoscaler e no dashboard do Prometheus a criação automática de novas réplicas de contentores conforme a carga aumenta.

---

## 👥 Contexto Académico

Desenvolvido no âmbito da unidade curricular de **Infraestruturas e Tecnologias de Informação** na **Universidade do Minho**.
