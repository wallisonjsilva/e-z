# Tarefas — e-z

Estados: `[ ]` pendente, `[/]` em andamento, `[x]` concluída. Cada tarefa de implementação deve registrar sua verificação antes de ser concluída.

## Documentação inicial

- [x] D07 — Renomear distribuição/comando para `e-z`, módulo para `e_z`, títulos Qt e documentação/empacotamento ativos; preservar referências e evidências anteriores. Verificar lock sem troca de versões, suíte, wheel/sdist, inicialização e manifesto do executável renomeado.
  - Primeira resolução offline falhou porque o novo cache `/tmp/e-z-uv-cache` estava vazio. Reutilizar o cache gravável já populado `/tmp/true-screen-uv-cache`, sem baixar ou atualizar dependências.
  - Verificado: lock e ambiente sincronizados offline; 19 registros de terceiros idênticos; 248 testes passaram em 2,89 s; wheel/sdist `e_z` e entry point conferidos. Qt offscreen confirmou nome/título e fechamento do main. Novo launcher e executável onedir iniciaram; manifesto sem links quebrados/Qt pendente. Resultados em STATE.md; segurança e homologação continuam em W11.3.

- [x] D06 — Apresentar o projeto como e-z no README para GitHub, com propósito, recursos atuais, início rápido, roadmap e links técnicos; preservar comandos existentes e distinguir funcionalidades implementadas de planos.
  - Verificado: links locais, caminhos dos testes e comandos de entrada conferidos contra o repositório. Alteração documental; nome técnico e código preservados. Os 248 testes citados são da execução anterior registrada, sem nova execução nesta revisão.

- [x] D01 — Ler referências e identificar divergências de stack/escopo.
- [x] D02 — Especificar entregas e critérios de aceitação.
- [x] D03 — Definir arquitetura, contratos e persistência.
- [x] D04 — Atualizar AGENTS e memória de execução.
- [x] D05 — Inverter prioridade para implementação/homologação Linux em E1/E2 e port Windows em E3; alinhar especificação, design, tarefas, instruções e estado.
  - Verificado: seis documentos alinhados, links locais existentes, 30 IDs de tarefas únicos e dependências Linux → Windows conferidas por script. Código, referências históricas e resultados anteriores preservados; nenhum novo teste nativo realizado.

## E1 — Linux (ordem de execução)

Os IDs W01–W11 foram mantidos para preservar rastreabilidade das implementações e verificações anteriores; são IDs históricos, não indicação de prioridade Windows. A mudança de alvo não conclui testes nativos pendentes. Antigas tarefas E3 Linux foram incorporadas à E1: L01 → W02/W06/W09/W11; L02/L03 → W08; L04/L05 → W11 e regressão A07. O port Windows passa a usar P01–P05.

- [x] W01 — Verificar Python/PySide6/PyInstaller; alinhar metadados e registrar ambiente reproduzível.
  - Conferir metadados oficiais, resolver versões compatíveis e instalar ambiente com lockfile.
  - Verificar imports, ferramentas de teste e build local; documentar comandos e limitações nativas.
  - Ambiente: cache padrão do uv está somente leitura; usar cache gravável em `/tmp/true-screen-uv-cache` nas verificações locais.
  - Falha na instalação: DNS do PyPI indisponível no sandbox. Reexecutar sincronização com acesso de rede autorizado antes de validar imports/build.
  - Verificado: instalação com rede autorizada, imports Qt, versões, sdist e wheel; detalhes em STATE.md. Homologação nativa pertence a W02/W11.
- [/] W02 — Criar janela e módulos; verificar inicialização e fechamento no Linux X11/Wayland.
  - Criar entrada Qt, cena central e propriedades com ações futuras desabilitadas.
  - Verificar abertura/fechamento offscreen local; manter verificação Linux pendente até execução nas sessões nativas.
  - Executado: janela abriu e fechou com event loop Qt offscreen no Fedora. Verificação nativa Linux pendente; W02 permanece em andamento. Cenário Windows transferido para P01.
- [x] W03 — Implementar geometria e documento imutável; testar limites e seleções invertidas (RF03).
  - Implementar retângulos inteiros, normalização floor/ceil, interseção e união para coordenadas negativas.
  - Validar fonte RGBA imutável, regiões e dimensões escaladas antes de alocações; testar invariantes sem Qt.
  - Verificado: `python -m pytest -q`, 45 testes passaram. Inclui seleção vazia/não finita, fonte mutável, IDs repetidos e destino externo sobreposto.
- [x] W04 — Implementar importação e clipboard; testar entrada inválida e preservação do documento (RF02).
  - Ler PNG/JPEG por conteúdo com QImageReader; validar dimensões e orçamento antes de decodificar/converter.
  - Isolar clipboard e diálogos em adaptadores; converter imagens em RGBA imutável sem aplicar DPI ao bitmap.
  - Preparar novo documento e preview antes de substituir; pedir descarte de trabalho não exportado, inclusive ao fechar.
  - Conectar Abrir/Colar à janela e testar imagens sintéticas, cancelamento, falhas e recusa por limites.
  - Verificado no Fedora/offscreen: 61 testes passaram (45 existentes + 16 novos), incluindo clipboard Qt local e ações da janela. Integração nativa Linux permanece na homologação E1; Windows será repetido em P01.
- [x] W05 — Implementar composição e exportação; verificar pixels 1:1 e canvas negativo (CA02/CA04).
  - Centralizar renderer QImage independente da cena; recortar sempre da base e respeitar ordem estável.
  - Exportar PNG por escrita temporária/commit; marcar exportado somente após sucesso.
  - Testar RGBA 1:1, canvas negativo, alpha, sobreposição, fonte original e falha de gravação.
  - Verificado: 74 testes passaram no total; round-trip PNG 1920×1080 com igualdade RGBA, canvas negativo, alpha, ordem estável, recorte da base e falhas de encode/commit sem alterar o destino anterior. Exportação ignora itens da cena e zoom da view.
- [/] W06 — Implementar seleção e transformação de coordenadas; verificar zoom e DPI (CA03/CA11).
  - [x] Criar viewport com inversão contínua da transformação (zoom/pan), cena em pixels da base e seleção limitada por floor/ceil.
  - [x] Conectar ferramentas Selecionar/Pan, zoom de navegação, Escape e indicação da seleção em português; não alterar estado sujo.
  - [x] Testar gestos Qt, quatro direções, bordas, cancelamento, zoom/pan e escalas Qt 100%/125%/150%/200% simuladas.
  - [ ] Verificar escalas/DPI misto disponíveis e monitores com origem negativa no Linux X11/Wayland; simulação offscreen não conclui CA11. CA03 completo depende da criação de regiões em W07. Repetir Windows em P03.
  - Falha detectada no teste de Ajustar após zoom alto: a mudança de visibilidade das barras de rolagem altera o viewport após o cálculo/centralização, cortando a borda inferior. Ajustar o fluxo de enquadramento e manter teste de regressão que exige a base inteira visível.
  - Revisão do teste de redimensionamento: a edição deixou asserções de seleção no teste vizinho, que não cria seleção. Reposicionar asserções no teste de preservação e repetir a suíte.
  - Verificado: `.venv/bin/python -m pytest -q`, 118 testes passaram (44 novos de viewport, incluindo quatro subprocessos para DPI simulado). Ajustar corrigido com reavaliação após redimensionamento do viewport. W06 permanece em andamento pela verificação nativa, agora priorizada no Linux.
- [x] W07 — Criar ampliações e alternância de modos; verificar três objetos, movimento e exclusão (CA05).
  - Implementar casos de uso puros com validação de escala, posição External, identidade e limites antes do commit.
  - Conectar controles de criação/edição, lista e ferramenta Objetos; reutilizar renderer no preview.
  - Arrastar contorno e efetivar uma alteração ao soltar; Escape/foco/ferramenta cancelam. Recusar External sobre a base sem perder estado.
  - Testar CA03/CA04/CA05 localmente, três objetos, modos, escala, exclusão, fonte imutável e falhas de preview; manter homologação nativa em W11.
  - Verificado: 153 testes passaram, com 17 novos de casos de uso e 18 de UI. Inclui CA03 em cinco níveis de navegação, três objetos, UUID/origem preservados na troca de modo, gesto com um commit, cancelamentos e falha de preview sem alterar documento/exportação.
  - Preview sintético revisado no plugin offscreen: controles, lista, destino externo e contorno visíveis. Exportação com destino negativo comparada ao renderer; build Python registrado em STATE.md. Sem homologação de sessão nativa.
- [/] W08 — Implementar captura Linux e restauração de janelas; detectar capacidades por sessão (RF01/RF12/CA10/CA11).
  - [x] Definir resultados tipados, contrato por callback Qt e seleção de backend sem fallback X11 em sessão Wayland.
  - [x] Integrar portal Screenshot por QtDBus, inscrição em Response antes da chamada, cancelamento/timeout, validação da URI local e limpeza apenas de recursos próprios.
  - [x] Ocultar/restaurar janelas e preservar documento em todos os resultados; impedir pedidos concorrentes e cancelar/restaurar antes de fechar durante captura.
  - [x] Verificar protocolo em barramento D-Bus isolado, fluxo UI offscreen e adaptador X11 com fixtures. Homologação exige sessão gráfica real e permanece pendente até executada.
  - Ambiente: o sandbox recusou socket Unix do D-Bus privado e escrita no diretório de runtime. Reexecutar teste de protocolo isolado com execução autorizada fora do sandbox; não acessar o portal real nem capturar tela nesse teste.
  - Falha no serviço fictício de teste: QtDBus entrega valores do QVariantMap como QDBusVariant, não bool/string puros. Desembrulhar variantes no serviço de teste e repetir o protocolo real antes de concluir o adaptador.
  - Ajuste adicional no serviço fictício: appendVariant não expõe seleção de tipo UInt nessa binding. Emitir Response como Signal("uint", "QVariantMap") exportado pelo QtDBus, para verificar a assinatura real ua{sv}.
  - Falha real de integração: leitura manual de QDBusArgument seleciona overload de escrita para mapa e falha nessa binding. Receber Response em slot tipado uint/QVariantMap/QDBusMessage, delegando deserialização ao Qt; manter cenário de protocolo real como regressão.
  - Isolamento do teste: remover o serviço fictício permitiu autoativação de portal instalado no barramento privado. Bloquear AutoStartService em todas as mensagens do transporte de teste (produção continua permitindo ativação normal); repetir serviço ausente sem processos de portal reais.
  - Falha na fixture X11: o provider criava novo monitor a cada consulta, simulando desconexão em vez de captura vazia. Manter identidade do monitor na fixture; a detecção de desconexão do adaptador estava correta.
  - Revisão de DPI: dimensões lógicas inteiras podem arredondar pixels físicos em escalas fracionárias. Reservar margem de um pixel lógico por eixo antes de grabWindow, validar o intervalo e manter as dimensões físicas reais do bitmap, sem exigir igualdade rígida à estimativa.
  - [ ] X11 nativo: validar adaptador implementado com dimensões físicas, DPI fracionário, origem negativa, falha e restauração de janelas em sessão real.
  - [ ] Wayland nativo: validar portal implementado com autorização, cancelamento, negação e serviço ausente; preservar documento e importação.
  - [ ] Registrar SO, desktop, sessão, versões de portal e resultados nativos; não usar disponibilidade de DISPLAY em Wayland como prova de captura X11.
  - Verificado: 205 testes pytest passaram (52 novos) e nove cenários de protocolo QtDBus real em barramento privado passaram, com serviço/imagem fictícios e autoativação bloqueada no teste final. W08 permanece em andamento pela homologação nativa; nenhum suporte X11/Wayland é certificado por esses testes.
- [/] W09 — Copiar composição e implementar atalhos locais; validar colagem entre aplicativos Linux X11/Wayland (CA06).
  - [x] Publicar QImage pelo adaptador Qt e conectar Copiar composição/Ctrl+C ao renderer central, sem alterar documento/estado sujo.
  - [x] Completar Delete/Escape na área de edição e lista, preservando atalhos de texto em campos; desabilitar cópia sem documento/durante captura.
  - [x] Verificar RGBA e dimensões iguais a PNG, negativos, camadas, zoom/pan, ausência de decoração, limites e recuperação de falhas no plugin offscreen.
  - [ ] Homologar colagem entre processos e duração após fechar nas sessões nativas X11/Wayland (CA06).
  - Registrar conteúdo/dimensões equivalentes à exportação e comportamento do clipboard após fechar o aplicativo. Word fica em P01/P05.
  - Verificado: 228 testes passaram (23 novos de clipboard/atalhos). PNG e clipboard com RGBA idêntico, incluindo canvas negativo, três camadas e transparência. Atalhos exercitados com foco na view/lista/campo de escala; falhas preservaram documento e estado de exportação. Build Python gerado. W09 permanece em andamento apenas pela validação nativa do clipboard.
- [x] W10 — Implementar limites de memória e processamento sem bloquear UI; exercitar recusa e recuperação.
  - [x] Usar QRunnable/QThreadPool com uma operação por vez, entrega enfileirada à thread gráfica e mensagens de erro sanitizadas.
  - [x] Mover decode, conversão RGBA, composição, escala e escrita PNG para worker; manter QPixmap, captura Qt, diálogos e publicação/obtenção de clipboard na UI.
  - [x] Modelar picos por fase: fonte/preview/clipboard residentes, decode/conversão, recorte/escala, publicação e encoder. Validar antes de alocar, liberar cenas antigas e impedir concorrência.
  - [x] Exibir atividade; ignorar resultados obsoletos e adiar fechamento até a operação concluir, sem interromper escrita atômica.
  - [x] Preservar verificações funcionais com executor imediato injetado nos testes; testar executor Qt real separadamente com barreiras, heartbeat, afinidade, fechamento e falhas/recuperação.
  - Regressão do protocolo: após separar decode em worker, cancel() invalidou o callback do portal e deixou o chamador direto sem resultado CANCELLED. Guardar callback pendente e entregá-lo uma única vez ao cancelar, ignorando resultados tardios; repetir suíte e nove cenários D-Bus privados.
  - Verificado: 248 testes passaram (20 novos com executor Qt real), incluindo falha ao admitir tarefa, event loop ativo, afinidade de callbacks, pipelines de captura/preview, snapshots obsoletos, limites e recuperação, fechamento e cancelamento durante decode. Nove cenários do protocolo D-Bus privado passaram após corrigir cancelamento.
  - Sonda offscreen reproduzível: base sintética 1920×1080 → saída 4344×1080, carregar/compor/copiar/exportar em 0,247 s, 67 ticks Qt, maior intervalo 23,2 ms; pico RSS Linux 216,3 MiB para o processo completo. Amostra local, sem homologação nativa ou garantia de RSS; medições da matriz real ficam em W11.
- [/] W11 — Empacotar e homologar E1 em Linux limpo; registrar dependências Qt/portal e matriz X11/Wayland (CA02–CA06/CA10–CA12).
  - [x] W11.1 — Inventariar bibliotecas/lock/ambiente e auditar versões em OSV e avisos oficiais, incluindo limites para bibliotecas nativas Qt/codecs.
  - [x] W11.2 — Documentar e verificar receita PyInstaller onedir Linux, módulos/plugins coletados, dependências externas, licenças e hashes.
  - [ ] W11.3 — Homologar pacote e segurança dos componentes distribuídos em ambiente limpo; registrar bloqueios e matriz nativa, sem publicação automática.
  - Auditoria: DNS do OSV indisponível no sandbox. Repetir consulta com rede autorizada e guardar JSON antes de tirar conclusões; revisar Qt nativo separadamente do resultado Python.
  - Primeiro build coletou QtNetwork/PDF/QML via imports condicionais Windows e plugins QtGui/teclado virtual, apesar de excluir wrappers Python. Ajustar receita para plugins desktop requeridos, remover bibliotecas nativas correspondentes e verificar dependências ELF e smoke antes de aceitar o candidato.
  - Segunda inspeção: as bibliotecas excluídas já não existiam, mas aliases SYMLINK em a.datas ficaram pendentes. Aplicar a mesma filtragem aos aliases e verificar links quebrados no inventário final; não confundir nome de symlink com biblioteca distribuída.
  - Manifesto ELF identificou plugins EGLFS e TUIO coletados automaticamente com dependências Qt removidas. Excluir esses plugins desktop sem uso e repetir build, manifesto e inicialização antes de aceitar a receita.
  - Verificado: OSV consultou 19 pacotes sem avisos; PyPI consultou 21 versões sem avisos ativos. QtCore 6.12.0 distribuído entra na faixa CVE-2026-105924, sem uso da operação afetada identificado e sem evidência de backport. [Relatório e evidências](docs/engineering/auditoria-dependencias-2026-11-09.md).
  - Candidato final: build onedir concluído, 160.885.837 bytes regulares, zero links quebrados e zero SONAME Qt sem fornecedor. Inicialização offscreen ativa após três segundos, encerrada por sinal. [Receita e limites](docs/engineering/empacotamento-linux.md); isso não homologa distribuição.
  - Regressão após receita/ferramentas: `.venv/bin/python -m pytest -q` — 248 testes passaram em 2,53 s; código da aplicação preservado.
  - Bloqueios W11.3: corrigir/revalidar QtCore; auditar cadeia nativa/CPython e completar avisos/licenças; build atual exige glibc 2.44 e não cobre Ubuntu da matriz; repetir em baseline compatível e testar em máquinas limpas/sessões reais.
  - Validar primeiro o ambiente Fedora KDE Wayland; incluir sessão X11 nativa e Ubuntu 24.04 LTS GNOME Wayland na matriz proposta. Registrar pendências sem afirmar suporte não comprovado.

## E2 — Editor Linux completo (depende da homologação E1 Linux)

- [ ] A01 — Adicionar redimensionamento proporcional e filtros; testar dimensões e reamostragem da fonte.
- [ ] A02 — Adicionar bordas, conectores e ordenação; validar limites e resultado exportado.
- [ ] A03 — Implementar comandos e histórico; testar undo/redo e agrupamento de gestos (CA07).
- [ ] A04 — Implementar pacote portátil e escrita segura; testar round-trip e realocação (CA08).
- [ ] A05 — Validar pacotes inválidos, hashes, versões e limites; preservar documento em falha (CA09).
- [ ] A06 — Implementar estado sujo e aviso de descarte; testar salvar, cancelar e descartar.
- [ ] A07 — Homologar E2 Linux nas sessões X11/Wayland, repetindo cenários E1 e CA07–CA09; liberar início do port somente após validação.

## E3 — Port Windows (depende da homologação E1 e E2 Linux)

- [ ] P01 — Validar editor compartilhado, abertura/fechamento, diálogos e clipboard no Windows 11 x64; verificar colagem no Word (CA06).
- [ ] P02 — Implementar adaptador de captura Windows, seleção de monitor e restauração de janelas em sucesso, cancelamento e falha (CA01).
- [ ] P03 — Validar captura/seleção com escalas 100%, 125%, 150% e 200%, DPI misto e origem negativa; ajustar somente integrações necessárias (CA01/CA11).
- [ ] P04 — Produzir pacote Windows com PyInstaller em Windows e testar em máquina limpa sem Python (CA12).
- [ ] P05 — Executar regressão E1/E2 no Windows (CA02–CA09/CA11), conferir equivalência de projetos/exportação com Linux e publicar suporte comprovado.

## Documentação de uso

- [ ] U01 — Após E1 Linux, documentar instalação e fluxo capturar → ampliar → exportar, incluindo portal/permissões e diferenças X11/Wayland, com templates/TOC próprios.
- [ ] U02 — Após E2/E3, documentar projetos editáveis, instalação Windows e diferenças de captura entre plataformas.
