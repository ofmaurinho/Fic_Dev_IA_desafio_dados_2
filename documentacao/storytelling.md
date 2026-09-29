# Storytelling Executivo com Dados

## 1. Pergunta Decisória Central
Como o formato do conteúdo educacional e a posição no ranking de recomendações afetam o engajamento e a conversão dos usuários na plataforma?

## 2. Narrativa Executiva

**Contexto**
Com a reestruturação governada da base analítica, o objetivo central passa a ser o entendimento do comportamento do usuário no consumo do catálogo. Identificar as variáveis que maximizam o engajamento é essencial para direcionar os investimentos em novos conteúdos e otimizar as sugestões da plataforma.

**Evidência**
O dashboard analítico apresenta filtros globais interativos e monitora o volume de usuários ativos, cruzando as taxas mensais de conclusão com a conversão detalhada por faixa de posição no ranqueamento.

**Descoberta**
* **Fatos Observados:** A taxa de conclusão global evoluiu de 16% (abril) para 33% (agosto). Conteúdos classificados como "Vídeo" possuem adesão superior, finalizando em 25% dos casos contra 19% dos formatos tipo "Curso". A posição da recomendação impacta criticamente o desempenho: posições 1 a 3 convertem a 4,7%, enquanto posições de 7 a 10 retêm apenas 1,5%. Atualmente, a taxa global despencou para 2,6%, acionando automaticamente um alerta de negócio definido para o limite inferior de 5%.
* **Hipóteses:** O modelo atual de curadoria sofre de dispersão de atenção ao expor muitos itens simultâneos, reduzindo o sucesso de conversão no final da lista. Além disso, o algoritmo atual pode não estar conferindo o peso necessário ao formato com maior chance estatística de finalização (vídeos).

**Ação Recomendada**
A curadoria deve atuar imediatamente sobre os parâmetros do motor de recomendação. É sugerida a revisão dos pesos de ranqueamento para privilegiar o formato de vídeo nas primeiras exibições, combinada a uma potencial redução da grade de recomendações visíveis, focando exclusivamente nas posições do topo (1 a 6) para alavancar a taxa de conversão a níveis superiores aos 5% esperados.