# True Screen

Aplicativo desktop offline para capturar telas e ampliar trechos de evidências, com Python e PySide6.

A implementação e a homologação começam no Linux, com X11 e Wayland. Após validar o editor essencial (E1) e o editor completo (E2), o projeto será portado para Windows (E3), reutilizando o núcleo e a interface.

Implementação atual: abrir PNG/JPEG, colar imagem, editar ampliações, exportar PNG e copiar a composição pela janela, com fonte imutável e confirmação de descarte de trabalho não exportado. Use **Abrir** (Ctrl+O), **Colar** (Ctrl+V), **Exportar PNG** e **Copiar composição** (Ctrl+C). O preview ajusta a base à área disponível; exportação e cópia mantêm os pixels físicos.

Após abrir uma imagem, use **Selecionar** e arraste em qualquer direção para marcar uma região. O painel mostra origem e tamanho em pixels da base. Use **Pan** para navegar por arraste, a roda para aproximar/afastar e os botões **Diminuir**, **Aumentar**, **100%** e **Ajustar** para controlar a visualização. **Ajustar** mantém a imagem enquadrada ao redimensionar a janela até uma navegação manual. Durante a seleção, **Escape** cancela o novo retângulo; sem arraste, limpa a seleção.

Seleção, zoom e pan não alteram os pixels nem tornam o documento não exportado. **100%** corresponde à escala lógica da visualização; telas de alta densidade podem usar mais pixels físicos para exibi-la.

Para ampliar, selecione uma região e escolha **Escala predefinida** (150%, 200% ou 300%) ou informe **Escala personalizada** entre 100% e 800%. Escolha **Modo** (**Sobreposto** ou **Externo**) e clique em **Criar ampliação**. O modo externo inicia à direita da base, com margem de 24 pixels. Use **Ajustar** para enquadrar o canvas expandido.

Crie várias ampliações e selecione uma delas na lista para editar escala/modo ou remover. Com **Objetos**, clique no destino da camada superior e arraste seu contorno; a imagem se atualiza ao soltar. **Escape**, perda de foco ou troca de ferramenta cancelam o arraste. **Delete**, com foco na área de edição/lista, ou **Remover ampliação** exclui a ampliação selecionada. Para selecionar outra origem, volte a **Selecionar**; isso também funciona sobre áreas cobertas por ampliações.

Escala e modo editam a ampliação selecionada; cada operação preserva a fonte original. Um destino externo deve ficar inteiramente fora da base, inclusive em posições negativas. Mover sobre a base é recusado; alternar para Externo reposiciona à direita somente quando necessário. Selecionar objetos não altera o estado de exportação; criar, editar ou remover exige nova exportação.

Preview e exportação usam a mesma composição e interpolação suave Qt; contornos de edição ficam fora do PNG. **Capturar** foi integrado: em X11, escolha um monitor; em Wayland, autorize e selecione a captura no diálogo do sistema. As janelas do aplicativo são ocultadas e restauradas antes de confirmar a substituição do documento. Cancelar ou falhar preserva o trabalho. A captura ainda exige homologação nativa nas sessões Linux.

Se a sessão ou o D-Bus estiver indisponível, **Capturar** fica desabilitado e o tooltip informa o motivo; **Abrir** e **Colar** continuam disponíveis. A conexão D-Bus habilita a tentativa pelo portal; serviço/interface ausentes também são tratados ao solicitar. O plugin offscreen não oferece captura. A espera pelo portal usa o event loop Qt, com timeout e cancelamento. Histórico/desfazer pertence à E2.

Carregamento, composição, escala e gravação de PNG agora são processados em segundo plano. Durante a operação, a barra de atividade e o status indicam o trabalho; controles de edição ficam temporariamente indisponíveis. Se você fechar a janela, o aplicativo aguarda a operação terminar e depois confirma eventual descarte. A exportação em andamento termina antes de fechar. Resultados pendentes de carregar/editar/copiar são descartados quando o fechamento já foi solicitado.

O aplicativo valida limites antes de alocar: 32.768 pixels por eixo, 40 milhões de pixels por superfície e orçamento conservador de 512 MiB para buffers de imagem. Uma operação pode ser recusada antes de atingir o limite de pixels por exigir várias superfícies simultâneas. Se isso ocorrer, reduza as dimensões da entrada ou a escala da ampliação. Esse orçamento não representa um limite garantido da memória total do processo/GPU. As chamadas de captura e clipboard do sistema ainda podem bloquear; o pool não as interrompe.

Para colar o resultado em outro aplicativo, use **Copiar composição** ou Ctrl+C com foco na área de edição/lista e depois cole no destino. A cópia inclui a base e todas as ampliações, sem contornos ou seleção. Copiar mantém o aviso de trabalho não exportado; use **Exportar PNG** para guardar um arquivo. A persistência do clipboard após fechar depende da sessão e ainda não foi homologada: mantenha o True Screen aberto até terminar de colar.

| Atalho local | Ação |
| --- | --- |
| Ctrl+O | Abrir PNG/JPEG |
| Ctrl+V | Colar imagem como novo documento |
| Ctrl+C | Copiar composição |
| Delete | Remover ampliação selecionada, com foco na área de edição/lista |
| Escape | Cancelar gesto; sem gesto, limpar seleção de objeto ou origem |

Nos campos de texto, copiar/colar texto e Delete/Escape continuam pertencendo ao campo. Ctrl+Z/Ctrl+Y e Ctrl+S serão integrados na E2.

## Desenvolvimento

Use Python 3.15 e [uv](https://docs.astral.sh/uv/). O arquivo `uv.lock` fixa as dependências transitivas; não precisa regenerá-lo para instalar.

```sh
uv sync --locked
uv run --locked true-screen
```

Alternativa de inicialização: `uv run --locked python -m true_screen`.

As dependências diretas são PySide6 6.12.0, PyInstaller 6.22.3 e pytest (desenvolvimento). Os metadados oficiais de [PySide6](https://pypi.org/project/PySide6/6.12.0/) e [PyInstaller](https://pypi.org/project/pyinstaller/6.22.3/) incluem Python 3.15. O grupo de desenvolvimento é instalado pelo `uv sync`.

## Verificações

```sh
uv run --locked python -m pytest -q
uv build --offline
uv run --locked pyinstaller --version
```

O build acima gera sdist e wheel Python. W11 já tem uma receita PyInstaller Linux e candidato local, ainda sem liberação pública: consulte o [procedimento de empacotamento](docs/engineering/empacotamento-linux.md) e a [auditoria de dependências](docs/engineering/auditoria-dependencias-2026-11-09.md). As consultas Python retornaram zero avisos, mas QtCore 6.12.0 está na faixa de um aviso oficial; segurança nativa, licenças e homologação continuam pendentes. O candidato Fedora exige glibc 2.44. O executável Windows virá em P04, após homologar E1/E2 Linux.

A suíte testa domínio, importação, composição, exportação e fluxos da janela com o plugin Qt `offscreen`, configurado pela fixture de testes. Os testes funcionais injetam um executor imediato; `test_processing.py` usa o pool Qt real para verificar threads, event loop, concorrência e fechamento. Usa somente imagens sintéticas e diretórios temporários; os testes de clipboard usam o clipboard local do plugin offscreen.

Para repetir somente os testes de importação, clipboard, janela e exportação sem tela:

```sh
uv run --locked python -m pytest -q tests/test_import.py tests/test_composition.py
```

Para verificar seleção, navegação e escalas Qt simuladas em processos isolados:

```sh
uv run --locked python -m pytest -q tests/test_canvas.py
```

Para verificar criação, modos, escala, movimento, exclusão e recuperação de falhas nas ampliações:

```sh
uv run --locked python -m pytest -q tests/test_regions.py tests/test_zoom_ui.py
```

Para verificar cópia da composição, igualdade com PNG e atalhos locais sem sessão gráfica real:

```sh
uv run --locked python -m pytest -q tests/test_clipboard.py
```

Para verificar processamento com workers Qt reais, limites e recuperação:

```sh
uv run --locked python -m pytest -q tests/test_processing.py
```

Uma sonda Linux offscreen gera uma base sintética 1920×1080, amplia uma região externamente e executa carregar/compor/copiar/exportar, medindo tempo, ticks Qt e pico RSS do processo completo:

```sh
uv run --locked python tests/processing_probe.py
```

Os números são uma amostra local; não comprovam desempenho no desktop, limite de RSS nem compatibilidade nativa. A sonda usa o pool real e clipboard offscreen, sem capturar tela ou alterar o clipboard da sessão gráfica.

Para verificar os fluxos de captura com fixtures e janelas offscreen:

```sh
uv run --locked python -m pytest -q tests/test_capture.py
```

No Linux, o protocolo do portal pode ser repetido num barramento D-Bus privado, após instalar o ambiente com uv. O comando requer `dbus-run-session` do sistema e permissão para criar sockets Unix locais:

```sh
dbus-run-session -- .venv/bin/python tests/portal_protocol_check.py
```

Esse teste usa um serviço e PNG fictícios, bloqueia autoativação de serviços do sistema e não captura a tela. Verifica serialização QtDBus real, resposta antecipada, handle alternativo, cancelamento, falha, URI inválida, timeout/Close e serviço ausente. Ele não substitui a validação do portal do desktop. A integração usa QtDBus incluído no PySide6; não foi adicionada dependência Python.

Os testes usam `QT_SCALE_FACTOR` em 1, 1.25, 1.5 e 2 com o plugin offscreen. Eles verificam coordenadas lógicas e pixels da fonte; não substituem DPI misto em monitores reais.

Se o cache padrão do uv estiver somente leitura, acrescente `--cache-dir /tmp/true-screen-uv-cache` após `uv` nos comandos Linux. A primeira instalação requer acesso ao PyPI; o aplicativo planejado funciona offline.

## Planejamento e validação nativa

Consulte [especificação](specs/true-screen.md), [design](specs/designs/true-screen.md), [tarefas](TASKS.md) e [estado](STATE.md).

Os IDs W01–W11 foram mantidos por rastreabilidade e agora pertencem à entrega Linux. P01–P05 representam o port Windows. Veja o mapa de reorganização no TASKS.md.

Primeiro no Linux: instalar o ambiente, executar os testes e iniciar a janela com `uv run --locked true-screen`, sem forçar o plugin offscreen. Verificar abertura, redimensionamento e fechamento sem processo remanescente. Registrar distribuição, desktop, sessão X11/Wayland, versões e resultados em STATE.md. O ambiente de desenvolvimento informa Fedora 45 KDE Wayland; a matriz proposta inclui sessão X11 nativa e Ubuntu 24.04 LTS GNOME Wayland. A presença de DISPLAY numa sessão Wayland não substitui validação X11.

W04/W05: abrir PNG e JPEG; colar imagem de outro aplicativo; cancelar substituição de documento não exportado; exportar e reabrir o PNG; provocar erro de acesso ao destino e verificar que o documento continua aberto e não exportado. Esses cenários exigem sessões Linux reais.

W09: criar composição com três ampliações, incluindo destino negativo; copiar pelo botão e por Ctrl+C; colar em editor de imagens/documentos nativo e comparar conteúdo/dimensões com o PNG exportado. Repetir mantendo o True Screen aberto e depois de fechá-lo, registrando distribuição, desktop, sessão, aplicativos/versões de destino e presença de gerenciador do clipboard. Validar X11 e Wayland separadamente. A comparação local no plugin offscreen passou; colagem entre processos e persistência após fechar continuam pendentes.

W06/W07: repetir seleções de 100×40 pixels e criar ampliações de 200×80 com diferentes níveis de navegação, nas bordas e em quatro direções; alternar monitores com escalas disponíveis, incluindo arranjo com origem negativa. Verificar três ampliações, modos, escala, movimento, exclusão, pan, Escape e Ajustar após redimensionar a janela. A seleção deve manter os limites e medidas da fonte. CA03/CA04/CA05 passaram localmente com o plugin offscreen; a homologação nativa e CA11 continuam pendentes.

W08: em X11 real, testar múltiplos monitores, escalas fracionárias, origem negativa, monitor desconectado e ocultação/restauração de todas as janelas próprias. Em Wayland real, testar o portal do desktop com autorização, cancelamento, recusa explícita, serviço ausente e timeout. A seleção de monitor/área depende do portal. Confirmar que o documento anterior continua intacto quando a captura não se conclui ou quando o descarte é cancelado. Registrar versões do portal/backend e resultado por sessão. Não usar imagens pessoais como evidência de teste.

Após homologar E1/E2 Linux, repetir os cenários do editor no Windows 11 x64, validar captura e DPI 100%/125%/150%/200%, colagem no Word e pacote em máquina limpa sem Python. Captura, DPI, clipboard e distribuição permanecem sem homologação nativa até executar e registrar seus testes.
