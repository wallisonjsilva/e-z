# e-z

**Capture, amplie e destaque evidências.**

e-z — **Evidência + Zoom** — é um aplicativo desktop offline para transformar capturas de tela em evidências técnicas mais legíveis. Capture ou abra uma imagem, amplie os detalhes importantes e exporte tudo em uma única composição.

Feito para relatórios de bugs, documentação, testes de software e demonstrações em que um detalhe pequeno precisa ficar claro.

**Python + PySide6 · Linux primeiro · Em desenvolvimento**

## Por que e-z?

Uma mensagem de erro, um valor em uma tabela ou um botão pode desaparecer em uma captura de tela inteira. O e-z permite ampliar esses trechos e manter o contexto da imagem original.

Cada ampliação parte diretamente da imagem-base, preservada no documento. Você pode aproximar a visualização para editar sem alterar as dimensões da exportação. Todo o processamento acontece no computador, sem conta, envio de imagens ou telemetria.

## O que já funciona

- **Captura de tela:** integração X11 com escolha de monitor e Wayland pelo portal do sistema, respeitando suas permissões.
- **Importação:** abrir PNG/JPEG ou colar uma imagem da área de transferência.
- **Ampliações independentes:** criar vários destaques com presets de 150%, 200% e 300%, ou escala personalizada de 100% a 800%.
- **Dois modos de composição:** sobrepor a ampliação à imagem ou posicioná-la fora da base, expandindo a área de saída.
- **Edição visual:** selecionar, mover, ajustar a escala e remover ampliações; navegar com zoom e pan.
- **Saída pronta para compartilhar:** exportar PNG ou copiar a composição, sem contornos e controles de edição.
- **Processamento em segundo plano:** carregamento, composição e exportação com indicação de atividade e validação de limites de imagem.

A captura, o clipboard e o comportamento com múltiplos monitores ainda passam por validação nas sessões Linux reais. A disponibilidade da captura depende da sessão e dos serviços do desktop.

## Como experimentar

O projeto está em desenvolvimento e ainda não oferece um pacote homologado para distribuição. Para executar a partir do código, use **Python 3.15**, **uv** e uma sessão gráfica Linux.

Na pasta do repositório:

```sh
uv sync --locked
uv run --locked e-z
```

A instalação inicial precisa de acesso ao PyPI. Depois de instalar as dependências, o aplicativo funciona offline. Em Wayland, a captura também exige o serviço XDG Desktop Portal e o backend do seu desktop.

O comando é `e-z` e o módulo Python é `e_z`. Você também pode iniciar com `uv run --locked python -m e_z`.

### Da imagem à evidência

1. Clique em **Capturar**, **Abrir** ou **Colar** para carregar a imagem-base.
2. Use **Selecionar** e arraste sobre o detalhe que deseja ampliar.
3. Escolha a **Escala** e o **Modo**: **Sobreposto** ou **Externo**.
4. Clique em **Criar ampliação**. Repita para destacar outras regiões.
5. Use **Objetos** para mover os destaques e **Ajustar** para visualizar a composição inteira.
6. Clique em **Exportar PNG** ou **Copiar composição** para usar o resultado.

Por exemplo, uma região de 100 × 40 pixels ampliada a 200% gera um destaque de 200 × 80 pixels, independentemente do zoom usado para navegar.

Mantenha o aplicativo aberto até colar o resultado em outro programa: a persistência da área de transferência após fechar ainda depende de validação por sessão. Para guardar o resultado, exporte o PNG.

### Atalhos

| Atalho | Ação |
| --- | --- |
| `Ctrl+O` | Abrir PNG/JPEG |
| `Ctrl+V` | Colar imagem como novo documento |
| `Ctrl+C` | Copiar a composição |
| `Delete` | Remover a ampliação selecionada |
| `Escape` | Cancelar o gesto ou limpar a seleção |

`Delete` e `Escape` atuam na área de edição/lista de objetos. Campos de texto preservam seus atalhos de edição. Use a roda do mouse para zoom e **Pan** para navegar por arraste.

## Roadmap

| Etapa | Objetivo | Situação |
| --- | --- | --- |
| **E1 — Editor essencial Linux** | Capturar, importar, ampliar, exportar e copiar | Funcionalidades implementadas; homologação e distribuição pendentes |
| **E2 — Editor completo Linux** | Bordas, conectores, ordem de camadas, filtros, desfazer/refazer e projetos `.evidence` | Planejado |
| **E3 — Windows** | Portar as integrações e validar captura, DPI, clipboard e distribuição | Após homologar E1 e E2 no Linux |

Salvar projetos editáveis e os atalhos `Ctrl+S`, `Ctrl+Z` e `Ctrl+Y` fazem parte da E2. A matriz Linux proposta inclui Fedora KDE Wayland, sessão X11 nativa e Ubuntu 24.04 GNOME Wayland; ela ainda não representa suporte homologado.

O escopo atual prioriza captura e composição local. OCR, reconstrução por IA, vídeo, nuvem e exportação PDF ficam fora dessas entregas.

## Desenvolvimento e testes

O projeto usa Python 3.15, PySide6 e dependências fixadas em `uv.lock`. A lógica do documento fica separada da interface e das integrações de captura/clipboard.

```sh
uv run --locked python -m pytest -q
uv build --offline
```

A última execução registrada teve **248 testes aprovados**. A suíte verifica geometria, importação, composição, exportação, limites e fluxos Qt com imagens sintéticas. Testes `offscreen` e serviços fictícios não substituem validação nativa de captura, DPI, clipboard ou distribuição. Os resultados e as limitações estão no [estado do projeto](STATE.md).

<details>
<summary>Comandos de verificação por área</summary>

```sh
# Importação e composição
uv run --locked python -m pytest -q tests/test_import.py tests/test_composition.py

# Seleção, navegação e escalas Qt simuladas
uv run --locked python -m pytest -q tests/test_canvas.py

# Ampliações e edição visual
uv run --locked python -m pytest -q tests/test_regions.py tests/test_zoom_ui.py

# Clipboard e atalhos
uv run --locked python -m pytest -q tests/test_clipboard.py

# Workers Qt, limites e recuperação
uv run --locked python -m pytest -q tests/test_processing.py

# Captura com fixtures
uv run --locked python -m pytest -q tests/test_capture.py

# Sonda de processamento e memória com imagem sintética
uv run --locked python tests/processing_probe.py

# Protocolo QtDBus em barramento privado
dbus-run-session -- .venv/bin/python tests/portal_protocol_check.py

# Versão do empacotador
uv run --locked pyinstaller --version
```

O teste D-Bus requer `dbus-run-session` do sistema e permissão para criar sockets Unix locais. Ele usa serviço e imagem fictícios, sem capturar a tela. A sonda usa Qt offscreen e não mede desempenho de uma sessão gráfica real.

Se o cache padrão do uv estiver somente leitura, acrescente `--cache-dir /tmp/e-z-uv-cache` após `uv` nos comandos Linux.

</details>

## Empacotamento e segurança

Existe uma receita PyInstaller em diretório (`onedir`) e um candidato Linux experimental. `uv build` gera os pacotes Python sdist/wheel; o executável tem um procedimento próprio em [Empacotamento Linux](docs/engineering/empacotamento-linux.md).

A [auditoria de dependências](docs/engineering/auditoria-dependencias-2026-11-09.md) registra consultas OSV/PyPI e revisão dos avisos nativos do Qt. O QtCore 6.12.0 está na faixa da CVE-2026-105924, sem uso da operação afetada identificado no código. A distribuição permanece pendente de correção/verificação, revisão de licenças e testes em máquina limpa. O candidato Fedora exige glibc 2.44 e não comprova compatibilidade com Ubuntu 24.04.

## Documentação e participação

- [Especificação](specs/e-z.md): requisitos, escopo e critérios de aceitação.
- [Design técnico](specs/designs/e-z.md): arquitetura e contratos.
- [Tarefas](TASKS.md): execução e dependências entre etapas.
- [Estado do projeto](STATE.md): decisões, verificações e próximos passos.

Para relatar um problema, informe os passos para reproduzir, distribuição, desktop, sessão X11/Wayland e comportamento esperado. Use imagens fictícias e remova dados pessoais ou credenciais dos exemplos.
