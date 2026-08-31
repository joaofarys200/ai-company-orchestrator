# 🖥️ Motor 3D OpenGL & Simulador Hierárquico do Sistema Solar

<p align="center">
  <img src="https://img.shields.io/badge/Linguagem-C%2B%2B17-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white" alt="C++17" />
  <img src="https://img.shields.io/badge/API-OpenGL_3.3%2B-5586A4?style=for-the-badge&logo=opengl&logoColor=white" alt="OpenGL" />
  <img src="https://img.shields.io/badge/Build-CMake-064F8C?style=for-the-badge&logo=cmake&logoColor=white" alt="CMake" />
  <img src="https://img.shields.io/badge/Classifica%C3%A7%C3%A3o_Acad%C3%A9mica-17%2F20-22c55e?style=for-the-badge" alt="Nota 17/20" />
  <img src="https://img.shields.io/badge/Unidade_Curricular-Computa%C3%A7%C3%A3o_Gr%C3%A1fica-orange?style=for-the-badge" alt="Computação Gráfica" />
</p>

> Motor de renderização 3D desenvolvido em C++ e OpenGL ao longo de 4 fases progressivas, com gerador procedimental de primitivas, interpolação de trajetórias com splines cúbicas de Catmull-Rom, tesselação de superfícies paramétricas de Bezier, aceleração por VBOs e iluminação com modelo de Phong.

---

## 🎯 Contextualização e Objetivo

A renderização eficiente de cenas 3D requer a conversão de modelos matemáticos abstratos (curvas paramétricas, matrizes de transformação, grafos de cena) em comandos acelerados por hardware na GPU.

Este projeto implementa um pipeline gráfico completo a partir do zero em C++ e OpenGL, estruturado em 4 fases incrementais:
1. **Gerador Procedimental de Geometria**: Cálculo matemático e exportação de vértices para primitivas 3D (`plano`, `cubo`, `esfera`, `cone`, `toro`).
2. **Motor Hierárquico & Parser XML**: Construção dinâmica de grafos de cena a partir de ficheiros XML com matrizes de transformação compostas (translação, rotação, escala).
3. **Animação & Superfícies de Bezier**: Interpolação de curvas cúbicas de Catmull-Rom para órbitas e câmaras suaves, além de tesselação de malhas de Bezier (ex: cometa, bule de chá).
4. **Iluminação & Mapeamento de Texturas**: Cálculo de normais por vértice e coordenadas UV, com iluminação de Phong (luzes pontuais, direcionais e focais).

---

## 🏛️ Arquitetura do Sistema

```
                    ┌────────────────────────┐
                    │ Gerador Procedimental  │  (Gera ficheiros .3d com vértices/índices)
                    │  - Primitivas (Esfera) │
                    │  - Malhas de Bezier    │
                    └───────────┬────────────┘
                                │ Ficheiro .3d com normais e coordenadas UV
                                ▼
┌──────────────────┐    ┌────────────────────┐    ┌─────────────────────────┐
│ Ficheiro XML     ├───►│  Motor C++ OpenGL  ├───►│ Pipeline GPU / Shaders  │
│  - Grafo de Cena │    │  - Transformações  │    │  - VBOs por Hardware    │
│  - Luzes e Cores │    │  - Splines Cúbicas │    │  - Iluminação de Phong  │
└──────────────────┘    └────────────────────┘    └─────────────────────────┘
```

---

## 🌓 Fases de Implementação

### Fase 1 — Gerador de Primitivas & Motor Base
- Geração matemática de vértices e triângulos para: `plano`, `cubo`, `esfera`, `cone`.
- Formato de ficheiro próprio `.3d` para armazenar geometria.
- Motor base capaz de ler ficheiros `.3d` e renderizar utilizando matrizes OpenGL.
- Leitura declarativa de cenas em XML através da biblioteca TinyXML.

### Fase 2 — Transformações Hierárquicas & Sistema Solar
- Suporte a transformações geométricas encadeadas (pilha de matrizes).
- Adição da primitiva **Toro** com controlo de raio interno/externo (usado para os anéis de Saturno).
- Modelação de um Sistema Solar completo com planetas, luas em rotação e eixos orbitais.

### Fase 3 — Animação com Catmull-Rom & Superfícies de Bezier
- **Splines Cúbicas de Catmull-Rom**: Interpolação contínua de posições e cálculo de derivadas para trajetórias suaves de câmaras e corpos celestes ao longo do tempo.
- **Superfícies de Bezier**: Avaliação matricial de malhas bicúbicas a partir de pontos de controlo para gerar modelos orgânicos (ex: cometa animado).
- **Aceleração por Hardware com VBOs**: Migração do modo imediato para *Vertex Buffer Objects* na memória da GPU, aumentando drasticamente a taxa de frames.

### Fase 4 — Iluminação de Phong & Mapeamento de Texturas
- Cálculo analítico de vetores normais por vértice e normais de face.
- Geração de coordenadas de mapeamento de textura $(u, v)$ em todas as primitivas.
- Suporte a múltiplas fontes de luz (`POINT`, `DIRECTIONAL`, `SPOTLIGHT`).
- Coeficientes de reflexão de material: ambiente, difusa, especular e emissiva.

---

## 🛠️ Tecnologias & Pré-Requisitos

- **Linguagem**: C++17
- **APIs Gráficas**: OpenGL 3.3+, GLUT / FreeGLUT, GLEW
- **Sistema de Compilação**: CMake 3.15+
- **Parsing XML**: TinyXML
- **Plataformas**: Linux (Ubuntu), Windows, macOS

---

## 🚀 Compilação e Execução

### Instalação de Dependências (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev libglew-dev
```

### Compilar o Motor Completo (Fase 4)
```bash
# Clonar o repositório
git clone https://github.com/joaofarys200/CG.git
cd CG

# Entrar na fase final e compilar
cd "Phase 4 - Lighting & Textures"
mkdir build && cd build
cmake ..
make -j4
```

### Gerar Geometria e Executar o Sistema Solar
```bash
# 1. Gerar os modelos 3D
./generator sphere 1.0 20 20 sphere.3d
./generator torus 0.5 1.5 30 30 torus.3d
./generator patch comet.patch 10 comet.3d

# 2. Lançar o motor com a cena XML
./engine scene_solar_system.xml
```

---

## 💡 Lições Aprendidas & Competências Desenvolvidas

- **Álgebra Linear & Matrizes $4 \times 4$**: Domínio de matrizes de modelo, vista e projeção, coordenadas homogéneas e produto vetorial para cálculo de vetores normais.
- **Gestão de Memória na GPU**: Compreensão do ciclo de vida dos buffers de vértices (VBOs) e redução de overhead na transferência CPU-GPU.
- **Matemática Paramétrica**: Conversão de formulações matemáticas contínuas em representações poligonais discretas em tempo real.

---

## 👥 Autores & Contexto Académico

Projeto desenvolvido no âmbito da unidade curricular de **Computação Gráfica** (3.º ano da Licenciatura em Ciências da Computação) na **Universidade do Minho**.  
**Classificação Final do Projeto**: **17 / 20**.

- João Pedro da Silva Faria ([@joaofarys200](https://github.com/joaofarys200))
- Pedro Manuel Pereira dos Santos
- João Manuel Franqueira da Silva
- David Alberto Agra
