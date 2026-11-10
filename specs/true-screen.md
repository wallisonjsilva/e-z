# SDD — True Screen

Status: implementação em andamento; prioridade invertida para Linux por orientação do usuário. Data: 2026-11-09.

## 1. Fontes e decisões de escopo

Fontes: [MVP](../refs/mvp.md), [ficha técnica](../refs/ficha-tecnica.md) e [template SDD](../refs/sdd-template.md).

Os documentos de referência contêm propostas divergentes. Esta especificação consolida o produto; as referências permanecem preservadas.

| Tema | Decisão | Motivo |
| --- | --- | --- |
| Stack | Python + PySide6 | Priorizar o MVP e aproveitar o projeto Python existente |
| Rust + Slint | Alternativa futura, fora deste plano | Evitar duas implementações simultâneas |
| Captura nativa | Primeira entrega Linux, X11 e Wayland | Validar o produto na plataforma inicial antes do port |
| Editor avançado | Segunda etapa Linux | Validar persistência e histórico antes de portar |
| Windows | Port posterior à homologação Linux de E1 e E2 | Reutilizar o núcleo validado e isolar diferenças de plataforma |
| Prazo | Sem compromisso com estimativas das referências | Escopos e tecnologias das estimativas são diferentes |

## 2. Problema e objetivo

Produzir screenshots de evidências técnicas com trechos pequenos legíveis. O usuário captura ou importa uma imagem, seleciona regiões, amplia e exporta a composição.

A imagem-base mantém dimensões e pixels decodificados. Ampliações são objetos independentes. Sobreposições podem ocultar visualmente a base, sem modificá-la no documento.

O aplicativo funciona localmente, sem conta, servidor, banco de dados ou privilégios administrativos. Os pacotes distribuíveis incluem o runtime necessário; o alvo inicial é Linux e o port Windows vem após sua validação.

## 3. Entregas

| Entrega | Conteúdo obrigatório |
| --- | --- |
| E1 — Screenshot Linux | Captura por botão em X11 e via portal em Wayland, importar PNG/JPEG, colar imagem, seleção retangular, múltiplas ampliações, modos sobreposto/externo, escala, mover, remover, exportar PNG e copiar composição; pacote e testes nativos Linux |
| E2 — Editor Linux completo | Redimensionamento proporcional, filtros de interpolação, bordas/conectores, ordem de camadas, desfazer/refazer e projeto portátil `.evidence`; homologação Linux |
| E3 — Port Windows | Reutilizar editor e exportação validados no Linux; adaptar captura, clipboard e DPI, empacotar e homologar no Windows 11 x64 |

Atalho global é incremento posterior à E1, condicionado à validação por plataforma. Atalhos locais pertencem à E1. OCR, reconstrução por IA, PDF, captura de janelas minimizadas, vídeo, nuvem e migração Rust ficam fora dessas entregas.

## 4. Requisitos funcionais

| ID | Requisito | Entrega |
| --- | --- | --- |
| RF01 | Em X11 e, no port, Windows, listar monitores e capturar o escolhido; em Wayland, usar seleção e permissões oferecidas pelo portal. Ocultar janelas próprias durante a captura e restaurá-las ao concluir, cancelar ou falhar | E1; Windows em E3 |
| RF02 | Abrir PNG/JPEG e colar imagem; rejeitar conteúdo inválido sem perder o documento atual | E1 |
| RF03 | Selecionar retângulos em qualquer direção, limitados à imagem-base; rejeitar área vazia | E1 |
| RF04 | Criar ampliações de 150%, 200%, 300% ou fator personalizado entre 1 e 8, sujeito ao limite de memória | E1 |
| RF05 | Alternar Overlay/External mantendo identidade, origem, escala e propriedades; ajustar apenas posição quando necessário | E1 |
| RF06 | Mover, selecionar e excluir ampliações; permitir pelo menos três simultâneas | E1 |
| RF07 | Expandir o canvas externo inclusive à esquerda/acima, sem redimensionar a base | E1 |
| RF08 | Exportar PNG e copiar a mesma composição para o clipboard, sem controles de edição | E1 |
| RF09 | Redimensionar proporcionalmente e configurar interpolação, borda, conector e ordem | E2 |
| RF10 | Desfazer/refazer alterações do documento; um arraste corresponde a um comando | E2 |
| RF11 | Salvar/reabrir documento portátil com base e objetos; avisar sobre alterações não salvas | E2 |
| RF12 | Detectar capacidades Linux e distinguir captura cancelada, indisponível, negada e falha; manter importação disponível | E1 |

Zoom de navegação e pan alteram somente a visualização. Capturar, importar ou colar inicia outro documento; solicitar descarte quando houver trabalho não exportado em E1 ou não salvo em E2.

No modo Overlay, o destino pode cruzar limites da base e permanece uma camada independente. No modo External, o destino deve ficar inteiramente fora da base. Ao alternar para External, posicionar à direita com margem de 24 pixels se houver interseção. Ao retornar, preservar posição; o usuário pode mover livremente.

## 5. Requisitos não funcionais

- RNF01: nenhum envio de imagens ou telemetria; logs não contêm imagens, clipboard ou caminhos pessoais por padrão.
- RNF02: fonte imutável; toda ampliação deriva da fonte, nunca de uma ampliação anterior.
- RNF03: exportação independe de DPI, zoom e tamanho da janela do editor.
- RNF04: interface permanece responsiva durante processamento; tarefas longas exibem estado de atividade e erros recuperáveis.
- RNF05: validar dimensões e orçamento de memória antes de alocar; não encerrar abruptamente por entrada inválida.
- RNF06: primeira plataforma de homologação: Linux x86_64. Ambiente inicial de desenvolvimento: Fedora 45 KDE Wayland; incluir validação nativa X11 e Ubuntu 24.04 LTS x64 com GNOME Wayland na matriz Linux proposta. Windows 11 x64 será homologado em E3 após E1/E2 Linux. Nenhum desses alvos é suporte comprovado apenas por constar na matriz.
- RNF07: atalhos locais, foco visível e rótulos compreensíveis em português.

## 6. Critérios de aceitação

| ID | Cenário e resultado verificável |
| --- | --- |
| CA01 | Capturar monitor escolhido no Windows com escalas 100%, 125%, 150% e 200%; dimensões correspondem aos pixels físicos e o aplicativo não aparece |
| CA02 | Importar base 1920×1080 e exportar sem objetos; pixels RGBA decodificados coincidem, sem exigir igualdade dos bytes PNG |
| CA03 | Selecionar 100×40 e ampliar 200%; destino tem 200×80, independentemente do zoom de navegação |
| CA04 | Mover ampliação externa para coordenadas negativas; exportação inclui todos os elementos sem encolher a base |
| CA05 | Alternar modos e editar três ampliações; origens e identidades permanecem, composição respeita ordem |
| CA06 | Exportar e copiar; dimensões e conteúdo coincidem, sem alças ou seleção; colagem funciona entre aplicativos nativos Linux, com comportamento após fechar documentado. No port E3, repetir e validar colagem no Word no Windows |
| CA07 | Desfazer/refazer criação, movimento, escala e exclusão restaura estados; novo comando após undo limpa redo |
| CA08 | Salvar, mover arquivo para outra pasta e reabrir; base, regiões e propriedades são recuperadas |
| CA09 | Arquivo corrompido, hash divergente, versão desconhecida ou limite excedido produz erro útil e preserva documento aberto |
| CA10 | Linux X11 captura e edita; Wayland aceita permissão via portal, trata cancelamento e mantém importação quando captura não está disponível |
| CA11 | Dois monitores com DPI distintos e origem negativa não deslocam a seleção; seleção nas bordas não excede a base |
| CA12 | Executável Windows funciona em máquina limpa sem Python instalado; aplicação Linux passa nos testes nativos definidos |

E1 Linux exige CA02–CA06, CA10, CA11 e parte Linux de CA12. E2 Linux acrescenta CA07–CA09 e repete E1. Somente após homologar ambas, E3 exige CA01 e parte Windows de CA12, repetindo CA02–CA09, CA11 e a parte Windows de CA06. Os cenários nativos de captura, clipboard e DPI devem ser registrados por sessão/plataforma; testes offscreen não os substituem.

## 7. Fluxo SDD e rastreabilidade

A auditoria das bibliotecas e a receita de empacotamento W11 têm [requisitos complementares](auditoria-empacotamento.md), com evidências e limitações próprias. O candidato local não altera os critérios nativos de E1.

Specify: este documento. Design: [design técnico](designs/true-screen.md). Tasks: [tarefas](../TASKS.md). Execute: implementar em incrementos e registrar evidências no [estado](../STATE.md).

Mudanças de comportamento atualizam requisitos, design e tarefas antes do código. Falhas exigem registrar causa e teste de regressão no planejamento; correções que apenas cumprem um requisito existente não devem alterar esse requisito.
