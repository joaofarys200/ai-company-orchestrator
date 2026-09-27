import type { StudyDocument } from './types';

export const DEFAULT_SAMPLE_DOCUMENT: StudyDocument = {
  document_id: 'doc-attention-transformer-2017',
  source_id: 'src-attention-paper',
  title: 'Attention Is All You Need',
  source_type: 'PDF',
  subject: 'Deep Learning & Arquiteturas Neurais',
  language: 'en',
  page_count: 6,
  extracted_text: `Attention Is All You Need
Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin

Abstract
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks in an encoder-decoder configuration. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over the existing best results, including ensembles by over 2 BLEU. On the WMT 2014 English-to-French translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs, a small fraction of the training costs of the best models from the literature. We show that the Transformer generalizes well to other tasks by applying it successfully to English constituency parsing with large and limited training data.

1. Introduction
Recurrent neural networks, specifically long short-term memory and gated recurrent neural networks, have been firmly established as state-of-the-art approaches in sequence modeling and transduction problems such as language modeling and machine translation. Numerous efforts have since continued to push the boundaries of recurrent language models and encoder-decoder architectures. Recurrent models typically factor computation along the symbol positions of the input and output sequences. Aligning the positions to steps in computation time, they generate a sequence of hidden states h_t, as a function of the previous hidden state h_{t-1} and the input for position t. This inherently sequential nature precludes parallelization within training examples, which becomes critical at longer sequence lengths, as memory constraints limit batching across examples.

Recent work has achieved significant improvements in computational efficiency through factorization tricks and conditional computation, while also improving model performance in case of the latter. However, the fundamental constraint of sequential computation remains.

Attention mechanisms have become an integral part of compelling sequence modeling and transduction models in various tasks, allowing modeling of dependencies without regard to their distance in the input or output sequences. In all but a few cases, however, such attention mechanisms are used in conjunction with a recurrent network.

In this work we propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies between input and output. The Transformer allows for significantly more parallelization and can reach a new state of the art in translation quality after being trained for as little as twelve hours on eight P100 GPUs.

2. Model Architecture
Most competitive neural sequence transduction models have an encoder-decoder structure. Here, the encoder maps an input sequence of symbol representations (x_1, ..., x_n) to a sequence of continuous representations z = (z_1, ..., z_n). Given z, the decoder then generates an output sequence (y_1, ..., y_m) of symbols one element at a time. At each step the model is auto-regressive, consuming the previously generated symbols as additional input when generating the next.

The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder, shown in the left and right halves of Figure 1, respectively.

Encoder and Decoder Stacks:
The encoder is composed of a stack of N = 6 identical layers. Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, position-wise fully connected feed-forward network. We employ a residual connection around each of the two sub-layers, followed by layer normalization. That is, the output of each sub-layer is LayerNorm(x + Sublayer(x)), where Sublayer(x) is the function implemented by the sub-layer itself. To facilitate these residual connections, all sub-layers in the model, as well as the embedding layers, produce outputs of dimension d_model = 512.

The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack. Similar to the encoder, we employ residual connections around each of the sub-layers, followed by layer normalization. We also modify the self-attention sub-layer in the decoder stack to prevent positions from attending to subsequent positions. This masking, combined with fact that the output embeddings are offset by one position, ensures that the predictions for position i can depend only on the known outputs at positions less than i.

3. Attention Mechanisms
An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors. The output is computed as a weighted sum of the values, where the weight assigned to each value is computed by a compatibility function of the query with the corresponding key.

Scaled Dot-Product Attention:
We call our particular attention "Scaled Dot-Product Attention". The input consists of queries and keys of dimension d_k, and values of dimension d_v. We compute the dot products of the query with all keys, divide each by sqrt(d_k), and apply a softmax function to obtain the weights on the values. In practice, we compute the attention function on a set of queries simultaneously, packed together into a matrix Q. The keys and values are also packed into matrices K and V. We compute the matrix of outputs as: Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V.

Multi-Head Attention:
Instead of performing a single attention function with d_model-dimensional queries, keys and values, we found it beneficial to linearly project the queries, keys and values h times with different, learned linear projections to d_k, d_k and d_v dimensions, respectively. On each of these projected versions of queries, keys and values we then perform the attention function in parallel, yielding d_v-dimensional output values. These are concatenated and once again projected, resulting in the final values.

4. Results & Discussion
On the WMT 2014 English-to-German translation task, the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models (including ensembles) by more than 2.0 BLEU, establishing a new state-of-the-art BLEU score of 28.4. The configuration of this model is listed in the first line of Table 3. Training took 3.5 days on 8 P100 GPUs. Even our base model surpasses all previously published models and ensembles, at a fraction of the training cost.

On the WMT 2014 English-to-French translation task, our big model achieves a BLEU score of 41.0, outperforming all of the previously published single models, at less than 1/4 the training cost of the previous state-of-the-art model.

5. Conclusion
In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder architectures with multi-headed self-attention. For translation tasks, the Transformer can be trained significantly faster than architectures based on recurrent or convolutional layers. On both WMT 2014 English-to-German and WMT 2014 English-to-French translation tasks, we achieve a new state of the art. In the former task our best model outperforms even all previously reported ensembles.`,
  sections: [
    {
      section_id: 'sec-abstract',
      title: 'Abstract',
      level: 1,
      page_start: 1,
      page_end: 1,
      paragraphs: [
        {
          paragraph_id: 'p-0',
          text: 'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks in an encoder-decoder configuration. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.',
          page_number: 1,
          section_id: 'sec-abstract',
          order: 0,
        },
        {
          paragraph_id: 'p-1',
          text: 'Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. Our model achieves 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over the existing best results by over 2 BLEU.',
          page_number: 1,
          section_id: 'sec-abstract',
          order: 1,
        },
      ],
    },
    {
      section_id: 'sec-intro',
      title: '1. Introduction',
      level: 1,
      page_start: 1,
      page_end: 2,
      paragraphs: [
        {
          paragraph_id: 'p-2',
          text: 'Recurrent neural networks, specifically long short-term memory (LSTM) and gated recurrent neural networks, have been firmly established as state-of-the-art approaches in sequence modeling. However, the inherently sequential nature precludes parallelization within training examples, which becomes critical at longer sequence lengths.',
          page_number: 1,
          section_id: 'sec-intro',
          order: 2,
        },
        {
          paragraph_id: 'p-3',
          text: 'Attention mechanisms have become an integral part of compelling sequence modeling and transduction models in various tasks, allowing modeling of dependencies without regard to their distance in the input or output sequences. In this work we propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies.',
          page_number: 2,
          section_id: 'sec-intro',
          order: 3,
        },
      ],
    },
    {
      section_id: 'sec-arch',
      title: '2. Model Architecture',
      level: 1,
      page_start: 2,
      page_end: 3,
      paragraphs: [
        {
          paragraph_id: 'p-4',
          text: 'The Transformer follows an encoder-decoder architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder. The encoder is composed of a stack of N = 6 identical layers, each with multi-head self-attention and a feed-forward network, wrapped in residual connections and layer normalization.',
          page_number: 2,
          section_id: 'sec-arch',
          order: 4,
        },
        {
          paragraph_id: 'p-5',
          text: 'The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack with causal masking.',
          page_number: 3,
          section_id: 'sec-arch',
          order: 5,
        },
      ],
    },
    {
      section_id: 'sec-attn',
      title: '3. Attention Mechanisms',
      level: 1,
      page_start: 3,
      page_end: 4,
      paragraphs: [
        {
          paragraph_id: 'p-6',
          text: 'An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors. Scaled Dot-Product Attention computes dot products of the query with all keys, divides each by sqrt(d_k), and applies a softmax function to obtain weights on the values: Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V.',
          page_number: 3,
          section_id: 'sec-attn',
          order: 6,
        },
        {
          paragraph_id: 'p-7',
          text: 'Multi-Head Attention linearly projects queries, keys, and values h times with learned projections, performing attention in parallel and concatenating outputs, allowing the model to jointly attend to information from different representation subspaces.',
          page_number: 4,
          section_id: 'sec-attn',
          order: 7,
        },
      ],
    },
    {
      section_id: 'sec-results',
      title: '4. Results & Discussion',
      level: 1,
      page_start: 4,
      page_end: 5,
      paragraphs: [
        {
          paragraph_id: 'p-8',
          text: 'On the WMT 2014 English-to-German translation task, the big transformer model outperforms previously reported models by more than 2.0 BLEU, establishing a new state-of-the-art BLEU score of 28.4. Training took 3.5 days on 8 P100 GPUs.',
          page_number: 4,
          section_id: 'sec-results',
          order: 8,
        },
        {
          paragraph_id: 'p-9',
          text: 'On the WMT 2014 English-to-French translation task, the big model achieves a BLEU score of 41.0, outperforming all single models at less than 1/4 the training cost of the previous state-of-the-art model.',
          page_number: 5,
          section_id: 'sec-results',
          order: 9,
        },
      ],
    },
    {
      section_id: 'sec-concl',
      title: '5. Conclusion',
      level: 1,
      page_start: 6,
      page_end: 6,
      paragraphs: [
        {
          paragraph_id: 'p-10',
          text: 'In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing recurrent layers with multi-headed self-attention. The model trains significantly faster while achieving superior translation quality.',
          page_number: 6,
          section_id: 'sec-concl',
          order: 10,
        },
      ],
    },
  ],
  media: [
    {
      media_id: 'fig-transformer-arch',
      media_type: 'figure',
      title: 'Figure 1: The Transformer - model architecture',
      caption: 'The Transformer follows an encoder-decoder structure using stacked self-attention and point-wise, fully connected layers for both the encoder (left) and decoder (right).',
      page_number: 3,
      evidence_status: 'OBSERVED',
      explanation: 'Diagrama esquemático demonstrando os 6 blocos do codificador (esquerda) com Multi-Head Attention e Feed Forward, e os 6 blocos do descodificador (direita) com atenção mascarada e atenção cruzada encoder-decoder. Ambos os blocos utilizam conexões residuais e Layer Normalization.',
    },
    {
      media_id: 'tab-bleu-benchmarks',
      media_type: 'table',
      title: 'Table 1: Maximum BLEU score on WMT 2014 translation benchmarks',
      caption: 'Comparison of Transformer against ByteNet, ConvS2S, and GNMT+RL on English-to-German and English-to-French tasks.',
      page_number: 5,
      evidence_status: 'OBSERVED',
      explanation: 'Tabela comparativa demonstrando que o Transformer (big) atinge 28.4 BLEU em EN-DE e 41.8 BLEU em EN-FR com um custo de treino de apenas 3.5 dias em 8 GPUs P100 (2.3e19 FLOPs), superando modelos anteriores convolucionais e recorrentes.',
    },
  ],
  metadata: {
    authors: ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar', 'Jakob Uszkoreit', 'Llion Jones', 'Aidan N. Gomez', 'Lukasz Kaiser', 'Illia Polosukhin'],
    year: 2017,
    venue: 'NeurIPS 2017',
    citations: 120000,
  },
  source_hash: 'sha256-sample-attention-is-all-you-need-2017',
  provenance: {
    source_file: 'attention_is_all_you_need.pdf',
    ingested_at: new Date().toISOString(),
    evidence_status: 'OBSERVED',
  },
  reading_progress: {
    current_page: 1,
    current_section: 'sec-abstract',
    scroll_position: 0,
    progress_percent: 30,
    last_read_at: new Date().toISOString(),
    bookmarks: [1, 3],
  },
  structure: {
    problem: {
      text: 'Modelos recorrentes (RNNs/LSTMs) são inerentemente sequenciais, impedindo a paralelização ao longo das posições de treino e limitando o processamento em sequências longas.',
      status: 'OBSERVED',
      page_ref: 1,
    },
    research_gap: {
      text: 'Mecanismos de atenção eram usados quase exclusivamente acoplados a redes recorrentes, sem explorar a atenção como mecanismo computacional autónomo primário.',
      status: 'OBSERVED',
      page_ref: 2,
    },
    research_question: {
      text: 'É possível eliminar completamente a recorrência e as convoluções mantendo ou superando o desempenho através unicamente de auto-atenção?',
      status: 'OBSERVED',
      page_ref: 2,
    },
    hypothesis: {
      text: 'Uma arquitetura baseada inteiramente em mecanismos de atenção auto-contidos permitirá paralelismo massivo e melhor captura de dependências globais em tempo linear de profundidade.',
      status: 'INFERRED',
      page_ref: 2,
    },
    contribution: {
      text: 'Proposição da arquitetura Transformer, mecanismo de Scaled Dot-Product Attention, Multi-Head Attention e codificação posicional sinusoidal.',
      status: 'OBSERVED',
      page_ref: 2,
    },
    method: {
      text: 'Pilha de 6 camadas no encoder e 6 no decoder, com Multi-Head Attention (8 cabeças, d_k=64, d_model=512), Feed-Forward de 2048 dimensões, conexões residuais e LayerNorm.',
      status: 'OBSERVED',
      page_ref: 3,
    },
    dataset: {
      text: 'WMT 2014 English-to-German (4.5M pares de frases) e WMT 2014 English-to-French (36M pares de frases) com vocabulário de subpalavras BPE.',
      status: 'OBSERVED',
      page_ref: 4,
    },
    experiment: {
      text: 'Treino em 8 GPUs NVIDIA P100 com otimizador Adam, warm-up de learning rate linear seguido de decaimento proporcional ao inverso da raiz quadrada do passo.',
      status: 'OBSERVED',
      page_ref: 4,
    },
    results: {
      text: '28.4 BLEU no benchmark EN-DE (+2.0 sobre o melhor ensemble anterior) e 41.8 BLEU em EN-FR com uma fração do custo computacional.',
      status: 'OBSERVED',
      page_ref: 4,
    },
    limitations: {
      text: 'Complexidade computacional e de memória quadrática O(n^2) em relação ao comprimento da sequência devido à matriz de atenção integral.',
      status: 'INFERRED',
      page_ref: 5,
    },
    conclusion: {
      text: 'O Transformer supera arquiteturas recorrentes e convolucionais em tarefas de transdução sequencial, treinando muito mais depressa e generalizando eficazmente.',
      status: 'OBSERVED',
      page_ref: 6,
    },
  },
  glossary: [
    {
      term: 'Self-Attention',
      translation: 'Auto-Atenção',
      explanation: 'Mecanismo que relaciona diferentes posições de uma única sequência para calcular uma representação integrada da mesma.',
      first_occurrence: 'p. 1, Abstract',
      occurrences: 32,
      importance: 'HIGH',
    },
    {
      term: 'Multi-Head Attention',
      translation: 'Atenção Multi-Cabeça',
      explanation: 'Projeção linear paralela de consultas, chaves e valores em múltiplos subespaços de representação com atenção independente.',
      first_occurrence: 'p. 3, § 3',
      occurrences: 18,
      importance: 'HIGH',
    },
    {
      term: 'Scaled Dot-Product Attention',
      translation: 'Atenção por Produto Interno Escalonado',
      explanation: 'Cálculo de atenção via produto escalar entre Q e K, dividido pela raiz da dimensão d_k para evitar saturação do softmax.',
      first_occurrence: 'p. 3, § 3.2',
      occurrences: 9,
      importance: 'HIGH',
    },
    {
      term: 'BLEU',
      translation: 'Bilingual Evaluation Understudy',
      explanation: 'Métrica quantitativa padrão para avaliação automática de qualidade de tradução baseada na precisão de n-gramas.',
      first_occurrence: 'p. 1, Abstract',
      occurrences: 14,
      importance: 'MEDIUM',
    },
  ],
  created_at: '2026-09-20T10:00:00.000Z',
  updated_at: '2026-09-22T10:00:00.000Z',
};
