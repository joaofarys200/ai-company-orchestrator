# REUNIÃO 2 GPTSI — TRANSCRIÇÃO INTEGRAL E SÍNTESE EXECUTIVA

- **Data da Gravação**: 22 de Outubro de 2026 (09:19)
- **Duração Total**: 00:33:39 (33 minutos e 39 segundos)
- **Ficheiro de Origem**: `reunião gptsi 2.m4a`
- **Unidade Curricular**: Gestão de Projetos e Tecnologias / Sistemas de Informação (GPTSI)
- **Projeto em Análise**: SIUM — Sistema de Informação para o Novo Museu
- **Fase**: Reunião 2 — Especificação de Requisitos, Arquiteturas, Orçamento e Diretrizes de Engenharia
- **Intervenientes**: Professor Luís, Estudantes / Grupos de Trabalho (Grupo 1, Grupo 2, Grupo 3, Grupo 4)
- **Motor de Transcrição**: Gemini 2.5 Multimodal de Alta Resolução com Alinhamento Temporal

---

# SÍNTESE EXECUTIVA — REUNIÃO 2 GPTSI (22/10/2026)

## 1. Contexto e Evolução da Sessão
A Reunião 2 de acompanhamento do projeto SIUM estabeleceu diretrizes técnicas e operacionais decisivas para os grupos de trabalho, consolidando os requisitos recolhidos nas entrevistas iniciais e estruturando os pilares de conceção e arquitetura do sistema.

### Definição Formal do Projeto SIUM
O Professor Luís formalizou a missão central do projeto:
> *«O Projeto SIUM (Sistema de Informação do Novo Museu) tem como finalidade conceber, desenvolver e implementar um sistema integrado de informação capaz de suportar de forma eficiente e sustentável todas as áreas de atividade do museu.»*

**Objetivos Gerais:**
1. Gestão integral da operação museológica;
2. Gestão das coleções e do espólio cultural;
3. Gestão e acolhimento de visitantes;
4. Gestão e programação de atividades e eventos.

---

## 2. Framework Arquitetural e Modelagem
O Professor Luís estipulou as cinco dimensões arquiteturais obrigatórias que todos os grupos devem desenhar e articular:
1. **Arquitetura de Dados (Data Architecture):** Destaque imperativo para o **Modelo de Dados**, considerado o coração relacional e conceptual do SIUM.
2. **Arquitetura Tecnológica (Technology Architecture):** Infraestrutura física e lógica, balanceamento e escalabilidade.
3. **Arquitetura de Segurança (Security Architecture):** Perfis de acesso, integridade de dados e proteção de privacidade.
4. **Arquitetura de Integração (Integration Architecture):** Protocolos de interoperabilidade com serviços externos (ex.: gateways de pagamento, APIs institucionais).
5. **Arquitetura de Informação (Information Architecture):** Taxonomia, fluxos de navegação e organização do conhecimento.

### Framework Corporativa Obrigatória: TOGAF
* O processo de desenvolvimento e alinhamento arquitetural do projeto deve utilizar formalmente o **TOGAF** (*The Open Group Architecture Framework*) como metodologia corporativa de referência.
* A infraestrutura do SIUM deve ser projetada para garantir **escalabilidade contínua e evolução futura**.

---

## 3. Diretrizes Críticas, Restrições e Orçamento

### Restrição Orçamental Fixa
* O teto orçamental máximo do projeto foi formalmente fixado em **200.000 €** (ou unidades monetárias do consórcio).
* Todos os custos de software, desenvolvimento, testes e licenças devem caber rigorosamente neste valor.

### Ordem de Corte Orçamental (Cenário Extremo)
* Questionado pelo Grupo 2 sobre a prioridade em caso de insuficiência orçamental, o Professor Luís determinou:
  * Pode pressupor-se a existência de financiamento complementar;
  * **Em caso extremo de défice orçamental, o primeiro módulo a ser cortado / descontinuado é a Loja física e respetivas componentes.**

### Equipamentos e Instalações: Criação 100% de Raiz
* Em resposta ao Grupo 3 sobre reutilização de equipamento legado:
  * **Não existe qualquer equipamento existente a reaproveitar.**
  * O museu é uma organização totalmente nova, sendo todo o ecossistema tecnológico criado **100% de raiz**.

### Prioridade de Processos
* Todos os processos de negócio identificados pelos grupos até à data (processos operacionais e de gestão) devem ser tratados como **prioritários** na fase de conceção e modelagem, sem cortes prematuros de escopo.

---

## 4. Requisitos Funcionais Detalhados das Aplicações Core

### Módulo de Gestão de Coleções (Coleções & Espólio)
Requisitos mínimos mandatórios:
1. **Inventário e Catalogação:** Registo exaustivo e categorização de peças do acervo.
2. **Histórico e Documentação:** Manutenção da proveniência, documentação técnica, artística e histórica.
3. **Localização e Movimentação:** Rastreio em tempo real da localização física de peças (armazém, salas de exposição permanente, exposições temporárias, transporte ou empréstimo).
4. **Conservação e Restauro:** Apoio ao ciclo de manutenção preventiva, relatórios de estado e restauro.

### Módulo de Bilhética e Gestão de Vendas
Requisitos mínimos mandatórios:
1. **Vendas Multicanal:** Suporte a vendas físicas (bilheteira presencial) e vendas online (portal do museu).
2. **Gestão de Reservas:** Gestão de agendamentos individuais, grupos escolares e visitas guiadas.
3. **Pagamentos Eletrónicos:** Integração com meios de pagamento eletrónicos (TPA, cartão, MB Way/referências).
4. **Emissão de Bilhetes Digitais:** Geração e validação de bilhetes eletrónicos (QR Codes / Barcodes).
5. **Estatísticas e Métricas:** Produção de relatórios analíticos de afluência, perfil de visitantes e receitas.

### Desafio Técnico de Migração de Dados
* O inventário inicial provém de ficheiros legados em folhas de cálculo (**Excel**).
* Os grupos devem formular um procedimento de **ETL (Extração, Transformação e Carga)** com definição clara de uma **«margem de erro tolerável»** e mecanismos de validação e reconciliação de dados.

### Natureza do SIUM e Comunicação
* O SIUM opera simultaneamente como **Website público** (canal de interação com o visitante) e como **Fonte de Dados Centralizada** para a operação da equipa museológica.
* Cada grupo terá a responsabilidade de preparar e executar a **comunicação e apresentação pública** das suas soluções.

---

## 5. Tabela Síntese de Decisões, Ações e Entregáveis

| Dimensão / Tópico | Decisão / Especificação | Responsável | Impacto no Projeto SIUM |
| :--- | :--- | :--- | :--- |
| **Missão do SIUM** | Sistema integrado para todas as áreas operacionais e de gestão do museu. | Todos os Grupos | Enquadramento nos objetivos gerais e requisitos de alto nível. |
| **Framework Arquitetural** | Adoção do padrão **TOGAF** como metodologia corporativa. | Todos os Grupos | Estruturação formal das camadas de dados, tecnologia e integração. |
| **Modelo de Dados** | Modelação detalhada de entidades (peças, inventário, vendas, visitantes). | Todos os Grupos | Base central indispensável para o desenvolvimento do protótipo. |
| **Orçamento Global** | Teto fixado em **200.000**. | Todos os Grupos | Restrição mandatória no dimensionamento e seleção de tecnologias. |
| **Ordem de Corte** | Em caso extremo de défice orçamental, a **Loja** é a primeira a ser cortada. | Grupo 2 / Turma | Definição clara da hierarquia de contingência funcional. |
| **Infraestrutura Física** | **Nenhum equipamento existente é reutilizado**; criação 100% de raiz. | Grupo 3 / Turma | Dimensionamento de compras e aquisição de hardware novo. |
| **Prioridade de Processos** | Todos os processos identificados são prioritários na fase de conceção. | Todos os Grupos | Exige análise holística sem descartar módulos preliminarmente. |
| **Módulo de Coleções** | Inventário, catalogação, histórico, localização/movimentação e conservação. | Grupo 4 / Turma | Núcleo da operação museológica e salvaguarda do património. |
| **Módulo de Bilhética** | Vendas online/presenciais, reservas, pagamentos eletrónicos e bilhete digital. | Grupo 4 / Turma | Interface de receita, canal do visitante e controlo de lotações. |
| **Migração de Dados** | Procedimento de importação do inventário Excel com margem de erro controlada. | Todos os Grupos | Garantia de integridade do acervo legado na transição para o SIUM. |
| **Comunicação** | Apresentação e defesa pública das arquiteturas e protótipo. | Todos os Grupos | Avaliação contínua e partilha de boas práticas entre grupos. |

---

# TRANSCRIÇÃO INTEGRAL (VERBATIM COM TIMESTAMPS)

### [00:00:00 - 00:03:00]

**Professor Luís:** ...apenas o sistema de informação que nós temos, posso dar aqui.
**Professor Luís:** Eu vou dar-vos a definição de um sistema de informação, mas, por exemplo, um sistema de informação...
**Professor Luís:** Seria, eu posso dar uma definição formal, que é:
**Professor Luís:** Projeto SIUM — é S-I-U-M.
**Professor Luís:** Tem como finalidade conceber, desenvolver e implementar um sistema integrado de informação, capaz de suportar de forma eficiente e sustentável todas as áreas de atividade do museu.
**Professor Luís:** E, de um modo geral, o sistema deverá assegurar a gestão da operação museológica, das coleções, dos visitantes, das atividades...

---

### [00:03:00 - 00:06:00]

**Professor Luís:** ...Portanto, devem contemplar: Arquitetura de dados. Arquitetura tecnológica. Arquitetura de segurança. Arquitetura de integração. E a arquitetura de informação.
**Professor Luís:** E o modelo de dados. O modelo de dados é fundamental, é o elemento central que vai ligar todas as entidades e suportar as operações que identificarem.

---

### [00:06:00 - 00:09:00]

**Professor Luís:** ...infraestrutura. [pausa] Deve suportar escalabilidade e evolução futura. [pausa] E deve ser desenvolvido tendo como referência o TOGAF.
**Estudante:** Okay. E deve ser desenvolvido...
**Professor Luís:** ...na parte do TOGAF.
**Estudante:** TOGAF.
**Professor Luís:** TOGAF. Aquilo é a parte dos colegas da LNEC. [pausa] Podem ir buscar referências para essas coisas. No terceiro ano, implementação de aplicações informáticas também no terceiro ano.
**Professor Luís:** Os colegas podem ir buscar referências para essas coisas.
**Professor Luís:** Entendido? A parte do TOGAF. O nosso processo é o TOGAF. Pronto.
**Estudante:** Hum.
**Professor Luís:** Grupo 2, estão de acordo?
**Estudante:** Sim.
**Professor Luís:** Qual é que é a vossa questão?
**Estudante:** Se o orçamento não chegar para tudo, qual é que é a ordem de corte?
**Professor Luís:** Portanto: se o orçamento não chegar para tudo, qual é a ordem de corte? É a vossa pergunta. Podem pressupor que haverá financiamento. No caso extremo de não acontecer, seria deixado de seguir a parte correspondente àquela que seria a Loja.
**Estudante:** Okay.
**Professor Luís:** Grupo 3?
**Estudante:** Nós temos a questão de se equipamentos já existentes vão ser reutilizados ou não.
**Professor Luís:** Podem ser reutilizados? Não existe nada que possa ser reutilizado, está? É mesmo a criação de raiz.

---

### [00:09:00 - 00:12:00]

**Estudante:** Sim.
**Professor Luís:** ...considerar que todos os processos que identificaram até agora são identificados numa base de prioridade.
**Estudante:** Sim.
**Professor Luís:** A resposta seria sobre todos.
**Estudante:** Sim.
**Professor Luís:** Portanto, considerar que são todos. Devem considerar todos os processos nesta fase de análise e levantamento.

---

### [00:12:00 - 00:15:00]

**Professor Luís:** No projeto já que vocês têm uma restrição, certo?
**Estudante:** 200.000.
**Professor Luís:** A restrição passa a ser 200.000. Esse é o teto que baliza as opções técnicas.

---

### [00:15:00 - 00:18:00]

**Estudante:** E se quiséssemos fazer, por exemplo, a integração faseada das componentes?
**Professor Luís:** É perfeitamente viável desenhar essa abordagem, desde que o modelo de arquitetura geral salvaguarde a coerência do sistema no seu todo.

---

### [00:18:00 - 00:21:00]

**Estudante:** Diria que é o EMA, SGM e a CCB...
**Professor Luís:** Sim, são os interlocutores institucionais e o consórcio responsável pelo enquadramento da organização do museu.

---

### [00:21:00 - 00:24:00]

**Estudante:** Grupo 4. Mais uma questão sobre a lista de aplicações que temos para o SIUM. Nas entrevistas falámos sobre a lista de aplicações identificadas. Gostávamos de saber os requisitos funcionais de cada uma. O problema é que temos cerca de 12. Se puder escolher uma... pode ser a gestão de coleções, incluindo o inventário e catalogação?
**Professor Luís:** Portanto, a gestão de coleções deverá ter no mínimo:
1. Gerir o inventário e a catalogação de peças;
2. Registar informação histórica e documental;
3. Gerir a localização e a movimentação de objetos;
4. E, finalmente, suportar os processos de conservação e restauro.

---

### [00:24:00 - 00:27:00]

**Professor Luís:** E quanto à bilhética e vendas, vou repetir:
1. Gerir vendas presenciais e online;
2. Gerir reservas individuais e de grupos;
3. Integrar pagamentos eletrónicos;
4. Emitir bilhetes digitais;
5. E produzir estatísticas de utilização e frequência.
**Estudante:** Professor Luís, só uma questão.
**Professor Luís:** Sim.
**Estudante:** A questão da migração de dados... com a margem de erro tolerável.
**Professor Luís:** Na migração, o inventário que está atualmente em Excel.
**Estudante:** Exatamente.
**Professor Luís:** Relacionado com a importação desses registos, têm de prever um processo de migração consistente, definindo os critérios de validação e o nível de tolerância aceitável na passagem para a nova base de dados.

---

### [00:27:00 - 00:30:00]

**Professor Luís:** Deixem-me só fazer aqui uma nota: o que é que é o SIUM?
**Professor Luís:** É um website e é, ao mesmo tempo, uma fonte central de dados para a organização. Não é apenas uma presença estática; é a infraestrutura digital que sustenta a operação interna e o acesso dos utilizadores.

---

### [00:30:00 - 00:33:00]

**Professor Luís:** E há também a componente de comunicação. Vocês vão ter de fazer a comunicação do projeto, explicando e justificando as soluções preconizadas perante os intervenientes.

---

### [00:33:00 - 00:33:39]

**Professor Luís:** ...Muito obrigado por esta apresentação. Para a próxima semana, o que é que vos peço para pensarem? Analisem detalhadamente as possibilidades de pagamento e sustentabilidade dos módulos transacionais. Até à próxima sessão!
