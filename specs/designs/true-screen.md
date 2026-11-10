# Design técnico — True Screen

Status: plano técnico; nenhuma funcionalidade implementada por este documento.

## Ordem de implementação e port

E1 e E2 são implementadas e homologadas primeiro no Linux. O port Windows em E3 depende dessa validação. Preservar o núcleo Python/PySide6 já implementado: domínio, aplicação, composição, persistência e UI são compartilhados. Priorizar adaptadores Linux X11/Wayland e manter Windows como integração posterior, sem duplicar o editor. Os IDs W01–W11 são históricos e permanecem estáveis no TASKS.md; o prefixo não define mais a plataforma. P01–P05 identificam o port Windows.

## 1. Arquitetura e stack

Auditoria e build W11 seguem os [requisitos complementares](../auditoria-empacotamento.md), a [auditoria registrada](../../docs/engineering/auditoria-dependencias-2026-11-09.md) e a [receita Linux](../../docs/engineering/empacotamento-linux.md). O candidato usa PyInstaller onedir com coleta restrita de Qt e inspeção ELF; avisos Python não substituem verificação das bibliotecas nativas. Distribuição permanece condicionada aos bloqueios documentados e à matriz nativa.

Monólito modular Python, com PySide6 para janela, cena, captura inicial, composição e clipboard. Pillow será usado para os filtros explícitos da E2, incluindo Lanczos3. MSS só será adicionado se testes demonstrarem lacuna no adaptador de captura. Não introduzir Rust, serviços ou framework de plugins.

W01 mantém Python 3.15 (`>=3.15,<3.16`) e `.python-version` 3.15 após consultar os metadados oficiais de [PySide6 6.12.0](https://pypi.org/project/PySide6/6.12.0/) e [PyInstaller 6.22.3](https://pypi.org/project/pyinstaller/6.22.3/), que incluem Python 3.15. Dependências diretas fixas e lockfile do uv controlam a instalação; pytest integra o grupo de desenvolvimento. Compatibilidade declarada não substitui execução local nem homologação nativa Linux/Windows.

```text
src/true_screen/
  __init__.py                 # entrada pública existente
  app.py                     # inicialização e composição de dependências
  domain/                    # geometria, documento, regiões; sem Qt
  application/               # comandos, histórico e casos de uso
  imaging/                   # recorte, composição, exportação
  ui/                        # janela, QGraphicsScene/View, propriedades
  platform/                  # captura, clipboard, diálogos
    linux_x11.py
    linux_wayland.py
    windows.py               # port E3, após homologação Linux
  persistence/               # pacote .evidence e validação
 tests/                      # criar na raiz, não dentro de src
```

Dependências apontam da UI/adaptadores para aplicação/domínio. O domínio usa tipos Python e não acessa sistema operacional. UI utiliza QPixmap somente na thread gráfica. Processamento usa buffers/QImage apropriados fora dela; resultados retornam por sinais. Não atualizar widgets em workers.

W10 usa QRunnable/QThreadPool em `imaging/tasks.py` com no máximo um worker e uma operação admitida por vez, compartilhado entre janela e adaptadores de captura. Sinais com conexão enfileirada entregam resultados à thread gráfica; sem asyncio ou outro runtime. Abrir/colar, edições, preview, copiar e exportar produzem QImage/bytes no worker. QScreen.grabWindow, obtenção de QImage do clipboard, diálogos, QPixmap e publicação de clipboard ficam na UI; conversão dos dados capturados/colados e decode do arquivo do portal vão para worker. A chamada nativa grabWindow e o acesso ao clipboard podem bloquear no sistema e não são interrompíveis pelo pool. Referências de contrato Qt: [QThreadPool](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThreadPool.html) e [QRunnable](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QRunnable.html).

Durante captura/processamento, ações de documento ficam indisponíveis e uma barra de atividade indeterminada/status informa a operação. Não enfileirar solicitações concorrentes. Aplicar resultado somente se o documento ainda for o snapshot de origem; preparar QPixmap/cena antes de commit. Fechar cancela portal quando aplicável e, se houver worker ativo, adia o fechamento até terminar; não matar threads nem interromper commit de PNG. Resultados de carregamento/edição/cópia são descartados se o fechamento já foi pedido; a exportação termina e atualiza o indicador se seu snapshot ainda for atual. A confirmação de descarte ocorre depois, já sem trabalho pendente. Erros preservam documento e reativam controles. Exceções atravessam threads apenas como mensagem pública, sem traceback, caminho ou conteúdo; só ValidationError controlado pelo aplicativo mantém sua mensagem. Executor imediato é injetado somente nas fixtures de testes funcionais; testes próprios usam o executor Qt real.

## 2. Contratos de plataforma

`CaptureBackend.capabilities()` informa disponibilidade e seleção de monitor. `capture(request)` retorna imagem, dimensões físicas e metadados de escala, ou resultado tipado: cancelado, indisponível, negado ou falha. O controlador não depende de detalhes nativos.

W08 concretiza o retorno com callback na thread Qt, sem runtime assíncrono adicional. Tipos de aplicação representam capacidades, monitores, pedido e resultado; adaptadores implementam captura/cancelamento. A seleção de backend exige Linux e plugin gráfico real: Wayland, inclusive Qt xcb sobre XWayland, usa portal; sessão X11 com plugin xcb usa QScreen. Plugin offscreen ou sessão desconhecida retorna indisponível, preservando Abrir/Colar.

O adaptador Wayland usa QtDBus já distribuído com PySide6. Solicita `Screenshot` com `interactive=true`, token aleatório e parent_window vazio (janelas próprias estarão ocultas); não promete seleção programática de monitor. Inscreve Response no caminho previsto antes da chamada e atualiza inscrição para handle alternativo sob o caminho de requests do remetente. A recepção usa slot tipado uint/QVariantMap/QDBusMessage para que Qt desserialize o mapa; a leitura manual de QDBusArgument falhou na binding verificada. Usa chamadas D-Bus não bloqueantes e timer de 120 segundos; cancelar/timeout fecha Request, libera inscrição e ignora respostas tardias. Resposta 1 é cancelamento; resposta 2 significa falha não especificada, não presumir recusa. Somente erro D-Bus explícito NotAllowed/AccessDenied representa negação; serviço/interface ausentes representam indisponibilidade. URI deve ser file local, sem host/query/fragmento; carregar pelos limites de imagem existentes. Arquivo entregue pelo portal não é apagado, pois sua propriedade não é garantida; não criamos cópia temporária própria. Contratos consultados: [Screenshot](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html) e [Request](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Request.html).

O controlador de captura guarda as janelas Qt top-level visíveis e seus estados, desativa encerramento por última janela, oculta, aguarda 250 ms via timer e inicia o adaptador. Restaura janelas/estados e a configuração de encerramento antes de entregar qualquer resultado à UI. O deadline global restaura janelas mesmo se o adaptador falhar em responder. Pedidos concorrentes são recusados; fechar durante captura cancela e restaura antes de sair. O documento só é substituído pelo fluxo transacional de importação após sucesso e eventual confirmação de descarte. Erros/recusa preservam o trabalho; cancelamento não abre alerta de erro. Mensagens não registram imagem, URI ou nomes privados.

No X11, listar monitores com dimensões físicas estimadas por tamanho lógico × DPR. Para validar orçamento antes de grabWindow, reservar margem de um pixel lógico por eixo, pois a geometria inteira pode arredondar dimensões físicas em DPI fracionário. Verificar dimensões recebidas dentro desse intervalo, origem local do documento e mudança/desconexão de monitor; preservar tamanho físico real do bitmap sem aplicar DPR outra vez. Falhas de captura são recuperáveis. Estimativa e comportamento real dependem de homologação X11/DPI; testes com QScreen fictício não certificam suporte nativo.

Linux X11 (E1): iniciar com QScreen.grabWindow e seleção de monitor, validando em sessão X11 real. Linux Wayland (E1): usar XDG Desktop Portal Screenshot com interação e permissões do usuário; a seleção disponível depende do portal. Não exigir monitor programático idêntico ao X11/Windows. Ler a imagem autorizada, liberar recursos temporários próprios e tratar cancelamento, negação e indisponibilidade sem erro destrutivo. Nunca tentar contornar permissões. Importação continua disponível. Uma sessão Wayland com DISPLAY disponível não comprova captura X11: detectar a sessão e preferir o portal em Wayland.

Nos adaptadores de captura, ocultar todas as janelas próprias, aguardar atualização do compositor e restaurar em bloco de finalização, inclusive em cancelamento/erro. Verificar imagens vazias e diferenças entre pixels lógicos/físicos. A presença de janelas/seletores do próprio portal é controlada pelo serviço, não pelo editor.

Windows (E3): iniciar o port com QScreen.grabWindow somente após homologar E1 e E2 Linux. Repetir testes de ocultação/restauração, monitores, DPI misto, clipboard e distribuição. Se falhar na homologação, substituir somente o adaptador. Não prometer captura de conteúdo protegido.

Clipboard expõe leitura/escrita de imagem via Qt. Testar persistência após fechar o processo no Linux; documentar se a sessão exigir aplicativo aberto. Diálogos e caminhos usam APIs portáveis; imports específicos de SO ficam nos adaptadores.

W09: Copiar composição/Ctrl+C renderiza o documento pelo mesmo `compose` usado no PNG e publica QImage no modo Clipboard, sem tocar na seleção primária X11. O adaptador valida imagem/dimensões/orçamento antes de setImage e permanece na thread gráfica. A UI prepara toda a composição antes de publicar; recusa de limites ou erro de renderização preserva clipboard anterior e documento. A API setImage não confirma colagem em outro processo; não fazer leitura automática nem prometer persistência após fechar. Copiar não limpa o indicador de trabalho não exportado, pois o clipboard não é arquivo durável. Mostrar confirmação no status e informar que o usuário pode colar em outro aplicativo.

Ctrl+O, Ctrl+V e Ctrl+C são locais à janela. Widgets de texto preservam seus atalhos de copiar/colar texto; não interceptar Delete/Escape no campo de escala. Delete remove a ampliação selecionada apenas com foco na área de edição ou lista de objetos. Escape nesses mesmos contextos cancela gesto pendente; sem gesto, limpa seleção de objeto ou, se não houver objeto, seleção de origem. Centralizar a lógica de Escape na view e associar ações de Delete/Escape somente à view/lista. Atalhos/ações de cópia ficam desativados durante captura, e cópia sem documento é indisponível. Ctrl+Z/Ctrl+Y e Ctrl+S continuam reservados à E2. Interoperabilidade e duração do clipboard exigem testes nativos X11/Wayland, como ressalta o contrato de [QClipboard](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QClipboard.html).

W04: `imaging` identifica PNG/JPEG pelo conteúdo, consulta dimensões com QImageReader e reserva orçamento para decodificação (até 8 bytes/pixel), conversão RGBA, bytes imutáveis e preview, incluindo o documento anterior. Imagens sem tamanho válido são recusadas antes de `read()`. O clipboard é consultado na thread gráfica; imagens Qt são validadas antes de cópia/conversão própria, embora a materialização pelo sistema não seja controlada pelo aplicativo. DPR não altera dimensões físicas. PNG mantém alpha; JPEG usa pixels decodificados sem transformação EXIF automática. Erros ao usuário são genéricos em português e não incluem caminhos nem conteúdo.

A sessão de aplicação mantém documento e indicador de trabalho não exportado. Importação monta candidato sem alterar o atual; worker renderiza QImage e UI prepara QPixmap/cena e confirma descarte antes de efetivar troca. Cancelar, falhar ou recusar descarte preserva documento e cena. Fechar também pede descarte, após concluir operação ativa. O indicador é limpo após exportação bem-sucedida, integrada em W05. W10 acrescenta processamento em worker e estimativas de memória por fase.

## 3. Documento e geometria

Incremento W03: a fonte do domínio é `SourceImage`, com largura/altura e bytes RGBA imutáveis; o documento e suas regiões são dataclasses congeladas, com coleção em tupla. Adaptadores devem validar dimensões antes de decodificar ou produzir esses bytes. O construtor verifica tamanho exato sem copiar o bitmap. Retângulos e união do canvas aplicam os limites de superfície; o documento verifica o orçamento básico fonte + saída + maior par recorte/destino. W10 acrescenta picos dos adaptadores, conversões Qt e publicação/encoder; não há cache de regiões. Hash do PNG interno e propriedades E2 serão incorporados nos respectivos incrementos.

`EvidenceProject`: schema_version=1, UUID, referência à base imutável, SHA-256 do PNG interno, lista de ZoomRegion e fundo de composição branco por padrão.

`ZoomRegion`: UUID, source (x,y,w,h inteiros em pixels da base), destination (x,y,w,h inteiros no canvas), mode (Overlay/External), resampling, z_index, show_border, show_connector. Empates de z_index seguem ordem persistida da lista. Fator efetivo deriva de destino/origem.

Seleção visual usa coordenadas contínuas. Transformar tela lógica → cena → pixels da fonte, aplicando o inverso de pan/zoom e a escala do bitmap. Normalizar direção, floor no início e ceil no fim, limitar à base e rejeitar largura/altura zero. Origem global do monitor não entra nas coordenadas locais do documento.

W06: `CanvasView` mantém cena em pixels da base e usa a inversa de `viewportTransform()` sobre `QMouseEvent.position()` contínua. A imagem do preview tem DPR=1; Qt já entrega ponteiro em coordenadas lógicas, portanto não multiplicar por DPR nem adicionar a origem global do monitor. Corrigir somente resíduos numéricos a até 1e-9 de coordenada inteira antes de floor/ceil; manter demais frações. Seleção existe apenas na view e é desenhada em `drawForeground`, sem alterar documento ou limites da cena.

Ferramentas Selecionar e Pan são exclusivas. Arraste esquerdo seleciona em qualquer direção; área vazia preserva seleção anterior. Escape cancela rascunho e restaura a seleção anterior; sem gesto em andamento, limpa a seleção. Trocar ferramenta ou perder foco cancela o gesto. Pan usa arraste esquerdo; roda altera somente zoom (0,5%–3200%), ancorado no ponteiro, e botões oferecem diminuir/aumentar/100%/Ajustar. Durante um arraste, roda não muda o zoom. Abrir outro documento limpa seleção e ajusta a visualização; cancelar importação preserva seleção/zoom. Seleção e navegação não alteram o indicador de trabalho não exportado. Em 100%, uma unidade da cena corresponde a uma unidade lógica da view; isso não promete um pixel físico do monitor em telas de alta densidade.

Ajustar mantém enquadramento ao redimensionar a janela até uma navegação manual por zoom/pan. A alteração das barras de rolagem também redimensiona o viewport; recalcular com QTimer de disparo único no próximo ciclo de eventos, sem chamar processamento de eventos dentro do gesto. A margem interna evita oscilação das barras. O timer pertence à view e é cancelado ao iniciar navegação manual ou trocar documento.

Destino permite x/y negativos. Escala conserva proporção; arredondar dimensões ao inteiro mais próximo, mínimo 1. Rejeitar valores não finitos, dimensões inválidas e escala fora do intervalo. Redimensionamento livre não proporcional fica fora do plano.

W07: casos de uso puros retornam outro EvidenceProject para criar, mover, excluir, alterar escala ou modo, compartilhando a mesma base e preservando UUIDs. Criar Overlay posiciona no início da seleção; External inicia à direita com margem de 24 pixels. Trocar para External ou aumentar sua escala reposiciona à direita somente se houver interseção com a base. Movimento External que intersecta a base é recusado e restaura a posição anterior; coordenadas negativas válidas são aceitas. Nenhuma operação é aplicada antes de validar o documento e preparar o preview.

A UI oferece escala predefinida 150%/200%/300% ou campo personalizado 100%–800%, modo Sobreposto/Externo, Criar ampliação e lista de objetos. Com um objeto selecionado, escala e modo editam esse objeto. Ferramenta Selecionar cria a origem mesmo sobre pixels cobertos por ampliações; ferramenta Objetos seleciona o destino da camada superior e arrasta seu contorno. O bitmap da composição é atualizado ao soltar, com um único commit por gesto; não recompor a cada evento de mouse. Escape, perda de foco e troca de ferramenta cancelam o arraste sem alterar documento/estado sujo. Delete na área de edição/lista (W09) ou botão Remover exclui o objeto selecionado. Seleção de objetos não entra no documento.

O preview usa o mesmo renderer da exportação e fica em um item de cena posicionado no mínimo x/y do canvas; a cena continua em pixels do documento, inclusive negativos. Contornos de seleção/arraste ficam em drawForeground e não entram na composição. Toda edição prepara candidato e preview antes de trocar o estado, preservando fonte, seleção e estado sujo em falha. W10 processa a composição em worker e publica na UI; histórico pertence a A03.

## 4. Renderização

1. Validar documento e orçamento.
2. Calcular união da base, destinos e extensões de bordas/conectores.
3. Aplicar floor aos mínimos e ceil aos máximos; transladar por (-min_x,-min_y).
4. Criar superfície RGBA e desenhar base 1:1.
5. Desenhar conectores entre centros de origem/destino atrás das ampliações; desenhar ampliações em ordem e suas bordas.
6. Recortar cada região sempre da fonte; reamostrar no tamanho final.
7. Exportar PNG ou copiar a mesma imagem composta.

W05/W07/W09: renderer recebe somente `EvidenceProject`, sem acesso à cena, utiliza QImage RGBA e interpolação suave Qt. Ordenação por z_index é estável. PNG é escrito com QSaveFile sem fallback de escrita direta; erro cancela o temporário e mantém eventual destino anterior. O mesmo renderer fornece preview, exportação e cópia da composição. O preview usa um bitmap composto; os controles de edição são desenhados separadamente na view.

Controles, alças, seleção e cursor não entram no renderer. A fonte retém alpha; exportação sobre fundo branco pode alterar pixels transparentes visíveis. Para comparação RGBA exata de CA02, usar fixture opaca ou fundo transparente configurado. Preservação refere-se a pixels decodificados, não metadados ou bytes JPEG.

E1: interpolação suave do Qt, identificada como tal, sem prometer Lanczos. E2: Pillow oferece Nearest, Bilinear, Bicubic e Lanczos3; Lanczos3 passa a ser o padrão para novas regiões. Preview e exportação usam o filtro persistido. Cache é descartável, indexado por fonte/retângulo/tamanho/filtro.

Limites iniciais propostos: 32.768 pixels por eixo, 40 milhões de pixels por superfície e orçamento de 512 MiB para buffers de imagem simultâneos. Calcular fonte + saída + recorte + destino + cache antes da operação, com multiplicações verificadas. Recusar excedentes com mensagem; limites não são garantia do RSS total. Medir e ajustar com evidências antes da release.

W10 centraliza estimativas de pico por fase em `imaging/budget.py`, sempre incluindo buffers residentes. Reservar 16 MiB adicionais para scratch de codecs/conversões; decode reserva até seis superfícies RGBA equivalentes (entrada de até 8 bytes/pixel, conversão, bytes imutáveis e scratch). Composição reserva duas fontes, duas saídas e o maior par de recorte×2/destino×3 para intermediários Qt. Exportação valida também saída×3 durante encoder; publicação de preview reserva saída×3 para QImage/QPixmap/conversão. Clipboard publicado reserva imagem×3 e guarda o maior tamanho já publicado nesta execução como cota conservadora do clipboard residente, sem ler conteúdo externo. A cota só diminui ao reiniciar. Cenas antigas são esvaziadas ao substituir para liberar bitmaps antes de outra operação. Não há cache de regiões. São limites conservadores de buffers modelados, não garantia do RSS/GPU nem medição de memória interna de codecs; medições nativas em W11 continuam obrigatórias.

## 5. Histórico e persistência

Comandos E2: criar, excluir, mover, redimensionar, trocar modo/filtro/propriedade e reordenar. Guardar estados dos objetos, sem duplicar bitmap. Agrupar gesto em um comando; cancelar gesto restaura estado. Limite inicial: 100 comandos. Seleção, pan e zoom de navegação não entram no histórico.

`.evidence` será ZIP contendo `manifest.json` e `assets/original.png`. Manifesto serializa campos do documento, caminho relativo e hash dos bytes do PNG interno. Não depender do arquivo importado. Histórico e caches não são persistidos.

Rejeitar caminhos absolutos, travessia, entradas duplicadas, links, arquivos inesperados, versão desconhecida e hash inválido. Ler entradas sem extrair para caminhos arbitrários; limitar manifesto a 1 MiB e imagem descomprimida aos limites do renderer. Verificar dimensões antes da decodificação completa. Não confundir SHA-256 com autenticação.

Salvar em temporário no mesmo diretório, concluir escrita e substituir destino atomicamente quando suportado; em falha preservar arquivo anterior e estado sujo. Abrir em documento temporário e trocar estado somente após validar tudo. Exibir erro recuperável se não houver espaço/permissão.

## 6. UI e distribuição

Janela: ações Capturar/Abrir/Colar, ferramentas de seleção e pan, cena central, propriedades e status. Controles locais: Ctrl+O, Ctrl+V, Ctrl+C para composição, Ctrl+Z/Ctrl+Y em E2, Delete e Escape. Ctrl+S salva projeto em E2. Desabilitar ações indisponíveis com indicação clara.

Empacotar Linux primeiro com build nativo; avaliar inicialmente diretório distribuível do PyInstaller e definir o formato final após verificar dependências Qt, plugins de plataforma e portal. Validar em ambiente limpo nas sessões X11 e Wayland da matriz. Não tratar wheel/sdist ou offscreen como distribuição homologada.

Após homologar E1/E2 Linux, empacotar Windows com PyInstaller inicialmente em diretório distribuível ZIP. Construir em Windows e testar em máquina limpa sem Python. Não assumir binário universal nem build Windows validado a partir de Linux. O núcleo e os testes de documentos/composição são reutilizados no port.

## 7. Validação e riscos

Testes unitários: geometria, modos, limites, histórico e serialização. Integração: fixtures sintéticas, pixels da base, tamanhos, negativos, filtros, camadas e round-trip. Golden images devem ter filtro e versões registrados. Testes GUI/nativos cobrem DPI, clipboard, portal e distribuição; mocks não homologam captura real.

Riscos principais: compatibilidade Python 3.15, DPI misto, sincronização ao ocultar janela, diferenças de interpolação, memória e suporte de portal. Resolver pelos incrementos de TASKS.md. Não declarar suporte sem registrar SO, sessão gráfica, versões, procedimento e resultado.

Matriz inicial Linux: Fedora 45 KDE Wayland como ambiente de desenvolvimento identificado; sessão X11 nativa e Ubuntu 24.04 LTS GNOME Wayland como validações propostas adicionais. Disponibilidade de variáveis de sessão não comprova acesso ao compositor, portal, clipboard ou captura dentro do sandbox. Homologar essa matriz antes de iniciar E3 Windows 11 x64.
