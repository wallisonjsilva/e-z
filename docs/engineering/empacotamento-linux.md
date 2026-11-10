# Empacotamento Linux — procedimento de engenharia

## Estado do candidato

Receita [PyInstaller](../../packaging/linux/e-z.spec) em modo `onedir`, verificada em Fedora 45 x86_64 com CPython 3.15.0, uv 0.13.7, PyInstaller 6.22.3, hooks 2026.9 e Qt 6.12.0. O candidato é **experimental e não está liberado para distribuição pública**: há aviso QtCore pendente, auditoria nativa/licenças incompletas e homologação em máquina limpa não realizada. Consulte a [auditoria](auditoria-dependencias-2026-11-09.md).

O diretório testado é `dist/linux-e-z-candidate/e-z/`. Seus arquivos regulares somam aproximadamente 153,4 MiB. O executável permaneceu ativo por três segundos com Qt offscreen, iniciado fora do projeto e sem variáveis de busca Python/Qt; foi encerrado por SIGTERM. Isso verifica a inicialização local, sem comprovar operações do editor, fechamento pela UI, captura, clipboard ou compatibilidade nativa.

Após a renomeação para e-z, o build foi repetido: 160.885.477 bytes regulares, nove bibliotecas Qt, zero links quebrados e zero SONAME Qt sem fornecedor. Os novos [manifesto](../../security/reports/2026-11-09-renomeacao-e-z/bundle.json) e [smoke](../../security/reports/2026-11-09-renomeacao-e-z/smoke.json) preservam os hashes deste candidato. As evidências anteriores de True Screen permanecem sem alteração.

O manifesto identifica requisito de **glibc 2.44**, além de bibliotecas gráficas externas. Este build não atende automaticamente ao Ubuntu 24.04 da matriz proposta. Para esse alvo, preparar ambiente de build na distribuição mínima, com Python 3.15 e wheels compatíveis; conferir novamente os símbolos e testar em cada distribuição. Não copiar glibc do Fedora para tentar corrigir incompatibilidade.

## Preparar e construir

Executar na raiz do projeto como usuário comum. Instalar uv 0.13.7 e Python 3.15 compatíveis com o sistema; `readelf` vem do binutils. A instalação inicial e a auditoria consultam a rede; o aplicativo empacotado funciona offline. O lockfile fixa as dependências, mas não torna os bytes do build idênticos em máquinas diferentes. O backend uv_build usado por uv 0.13.7 foi 0.13.7.

Os exemplos usam um cache novo com o nome e-z; a verificação offline desta renomeação reutilizou `/tmp/true-screen-uv-cache`, já populado no ambiente anterior. O nome do diretório temporário não altera a identidade do pacote.

```sh
uv --cache-dir /tmp/e-z-uv-cache sync --locked
.venv/bin/python -m pytest -q
uv --cache-dir /tmp/e-z-uv-cache audit --locked --output-format json
PYINSTALLER_CONFIG_DIR=/tmp/e-z-pyinstaller .venv/bin/pyinstaller --distpath dist/linux-e-z-candidate --workpath build/linux-e-z-candidate packaging/linux/e-z.spec
```

Usar um novo `--distpath` para outro candidato ou revisar o diretório gerado existente antes de aceitar sua substituição. `build/` e `dist/` são saídas ignoradas pelo Git. Não regenerar o lock silenciosamente e não executar o aplicativo como root. O build ainda emite aviso de hidden import `xxsubtype` ausente; a inicialização offscreen passou, mas o aviso não substitui revisão de imports e teste funcional do pacote.

`uv build --offline` produz sdist/wheel para instalação Python; o comando PyInstaller acima produz o diretório com interpretador embutido. O consumidor final não deve precisar da `.venv`, mas essa propriedade ainda exige teste em máquina limpa. [Funcionamento e restrições de plataforma do PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html).

## Conteúdo e dependências

A receita coleta os módulos usados QtCore, QtGui, QtWidgets e QtDBus. Mantém plugins XCB, Wayland, offscreen/minimal e JPEG; PNG é integrado ao QtGui. Inclui, por dependência desktop, QtOpenGL, QtSvg, QtWaylandClient, QtWlShellIntegration e QtXcbQpa. Remove wrappers e bibliotecas WebEngine/PDF/QML/Quick/rede, teclado virtual e plugins EGLFS/TUIO sem uso. Testes e PyInstaller como módulos Python são excluídos. UPX e `onefile` não são usados.

Não usar `--collect-all PySide6`: isso recoloca componentes sem uso e amplia as dependências. Filtragem nativa deve incluir aliases de symlink e todos os plugins consumidores; não basta excluir imports Python. Cada mudança de Qt/hooks requer novo manifesto e verificação funcional.

O manifesto atual lista estes SONAMEs externos: `ld-linux-x86-64.so.2`, `libEGL.so.1`, `libGL.so.1`, `libc.so.6`, `libdl.so.2`, `libm.so.6`, `libpthread.so.0`, `libresolv.so.2`, `libwayland-client.so.0`, `libwayland-cursor.so.0`, `libwayland-egl.so.1` e `libxcb.so.1`. A lista deriva de ELF NEEDED; bibliotecas carregadas dinamicamente, drivers, fontes e serviços podem acrescentar requisitos. Outras bibliotecas, incluindo suporte D-Bus e ICU, foram coletadas e constam do manifesto; isso não comprova ausência de CVEs.

A máquina de destino precisa de sessão gráfica, drivers compatíveis e acesso normal ao D-Bus. Em Wayland, precisa também de `xdg-desktop-portal` e backend compatível com o desktop, disponíveis como serviços do sistema. Esses serviços não são incorporados ao executável. Captura deve respeitar o portal e suas permissões; a presença de XWayland não equivale à homologação X11.

## Verificar e registrar

Para uma revisão futura, substituir a pasta de evidências pela data da revisão. O script de manifesto exige `readelf`, falha em links quebrados/dependências Qt não fornecidas e registra hashes, dependências ELF e maior versão GLIBC; dependências externas do sistema ainda precisam de validação.

```sh
.venv/bin/python tools/bundle_inventory.py dist/linux-e-z-candidate/e-z --output security/reports/2026-11-09-renomeacao-e-z/bundle.json
.venv/bin/python tools/smoke_bundle.py dist/linux-e-z-candidate/e-z/e-z --output security/reports/2026-11-09-renomeacao-e-z/smoke.json
```

Para executar no desktop, em sessão de teste com imagens fictícias, sem forçar offscreen:

```sh
./dist/linux-e-z-candidate/e-z/e-z
```

Antes de liberar, registrar distribuição, kernel, arquitetura, glibc, desktop, X11/Wayland, versões do portal/backend, monitores/DPI e resultado de cada cenário em STATE.md. Testar em máquina limpa sem Python/uv/venv do projeto e sem variáveis que apontem para a instalação do desenvolvedor.

| Verificação nativa | Resultado necessário |
| --- | --- |
| Inicialização/fechamento | Janela abre, redimensiona e fecha sem processo remanescente |
| Importação | PNG/JPEG e clipboard; cancelamentos/arquivos inválidos preservam documento |
| Editor/exportação | Seleção 100×40 → 200×80 em vários zooms; três objetos, negativos, PNG sem controles |
| Clipboard | Colagem em outro aplicativo com dimensões/conteúdo corretos; registrar efeito de fechar o e-z |
| Captura X11 | Monitor, múltiplos DPI, origem negativa, restauração em sucesso/falha/cancelamento |
| Captura Wayland | Portal real, autorização, cancelamento, recusa/indisponibilidade e restauração |
| Recursos | Responsividade e memória com entradas sintéticas próximas dos limites |
| Distribuições | Fedora KDE Wayland, X11 nativo e Ubuntu 24.04 GNOME Wayland, após build compatível |

## Licenças, integridade e entrega

Antes de qualquer publicação, completar a licença do próprio projeto e um diretório de avisos de terceiros, com textos, atribuições, versões, fontes correspondentes e instruções de reconstrução/revinculação aplicáveis aos binários realmente entregues. Metadados Python não substituem licenças de Qt e seus componentes nativos. PySide6/Shiboken declaram alternativas LGPL/GPL; verificar a opção de distribuição adotada e os termos dos módulos, plugins e bibliotecas coletados. A vinculação dinâmica sozinha não conclui essa verificação. [Termos LGPL publicados pelo Qt](https://doc.qt.io/qt-6/lgpl.html).

Incluir CPython, Qt/PySide/Shiboken, bibliotecas de terceiros coletadas e licença/exceção do bootloader PyInstaller. Os avisos completos não foram encontrados nas wheels Qt inspecionadas, e ainda não foram montados no candidato; essa etapa permanece bloqueio de publicação. Não inventar licença do projeto nem copiar apenas um texto genérico de Qt.

Após resolver os bloqueios e homologar, arquivar o diretório **inteiro**, preservando `_internal/`, permissões e symlinks. Exemplo futuro de entrega, ainda não executado nesta revisão:

```sh
tar -C dist/linux-e-z-candidate -czf dist/e-z-0.1.0-linux-x86_64.tar.gz e-z
sha256sum dist/e-z-0.1.0-linux-x86_64.tar.gz > dist/e-z-0.1.0-linux-x86_64.tar.gz.sha256
```

Entregar junto avisos/licenças, instruções e manifesto correspondente. SHA-256 detecta alteração, mas não comprova origem; assinatura e canal de publicação ainda não foram definidos. Testar a extração do arquivo final em diretório novo, não somente a árvore original de build. Para rollback, conservar a versão anterior em outro diretório e iniciar seu executável; não misturar bibliotecas de versões distintas. Não há instalador, atualização automática ou publicação implementados.

Windows permanece em E3/P04: construir em Windows e repetir a auditoria, licenças e testes em máquina limpa; este `.spec` Linux não comprova suporte Windows.
