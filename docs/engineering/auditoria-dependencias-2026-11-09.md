# Auditoria de dependências — 9 de novembro de 2026

Nota de rastreabilidade: esta auditoria e seus JSONs registram o projeto antes da renomeação True Screen → e-z. O nome local e o hash do lock mudaram; os 19 registros de dependências de terceiros foram preservados integralmente. A renomeação não repete a consulta online nem resolve os bloqueios abaixo. Inventário, manifesto e inicialização posteriores estão em [evidências da renomeação](../../security/reports/2026-11-09-renomeacao-e-z/inventory.json); a [receita ativa](empacotamento-linux.md) usa os novos nomes.

## Resultado

**Distribuição pública pendente.** OSV retornou zero avisos para os 19 pacotes públicos do lockfile. A API PyPI retornou zero avisos ativos nas 21 versões consultadas, incluindo uv e uv-build. Esses resultados não cobrem integralmente o Qt nativo: **QtCore 6.12.0, incluído no candidato, está na faixa afetada pela CVE-2026-105924**. Não foi identificada chamada da operação afetada no código da aplicação; presença da versão afetada não demonstra exploração. Não há evidência local de backport da correção. [Aviso oficial Qt](https://www.qt.io/blog/security-advisory-cve-2026-105924).

A auditoria registra vulnerabilidades conhecidas, sem certificar ausência de outras. Não foi realizado teste de exploração. O aplicativo continua offline; somente as ferramentas de auditoria consultaram serviços externos com nomes/versões públicos.

## Inventário

Ambiente: Fedora 45 x86_64, CPython 3.15.0, Qt 6.12.0, uv 0.13.7 e glibc 2.44. Data local: 09/11/2026, America/Sao_Paulo; os JSONs usam UTC e alguns têm data 10/11. Lock auditado: SHA-256 `a010191ea8f5c6417aabe1441dc62ce30584a5fb26e373bb1d0c59a2194953ae`.

| Pacote | Versão no lock | Papel |
| --- | --- | --- |
| pyside6 | 6.12.0 | Dependência direta de execução; bindings Qt |
| pyside6-essentials | 6.12.0 | QtCore/Gui/Widgets/DBus e outros componentes |
| pyside6-addons | 6.12.0 | Transitiva instalada; somente componentes necessários coletados |
| shiboken6 | 6.12.0 | Suporte aos bindings |
| pyside6-pdf | 6.12.0.140 | Transitiva instalada; PDF excluído do candidato |
| pyside6-webengine | 6.12.0.140 | Transitiva instalada; WebEngine excluído do candidato |
| pyinstaller | 6.22.3 | Empacotamento; bootloader integra o executável |
| pyinstaller-hooks-contrib | 2026.9 | Regras de coleta do build |
| altgraph | 0.17.5 | Análise de imports no build |
| packaging | 26.3 | Ferramentas de build/teste |
| setuptools | 84.2.1 | Ferramentas de build |
| pytest | 9.2.0 | Testes |
| iniconfig | 2.3.1 | Testes |
| pluggy | 1.7.0 | Testes |
| pygments | 2.21.0 | Ferramentas de teste |
| colorama | 0.4.6 | Dependência condicional do lock |
| pefile | 2024.8.26 | Build Windows, condicional |
| pywin32-ctypes | 0.2.3 | Build Windows, condicional |
| macholib | 1.16.4 | Build macOS, condicional; não representa suporte ao macOS |

São 19 pacotes de terceiros no lock, além do projeto local `true-screen` 0.1.0. O inventário instalado contém 16 nomes únicos incluindo o projeto; os quatro condicionais acima não estão instalados neste Linux. uv 0.13.7 e seu backend embutido uv_build 0.13.7 foram usados e consultados separadamente no PyPI. O requisito do backend permanece `uv_build>=0.13.7,<0.14.0`; usar a versão de uv registrada para repetir este ambiente.

O código importa explicitamente PySide6.QtCore, QtGui, QtWidgets e QtDBus. Pillow e MSS são possibilidades futuras do design, não dependências atuais. Não há outro framework de imagem no lock.

## Avisos oficiais e aplicabilidade

| Aviso | Faixa relevante e efeito | Situação neste projeto |
| --- | --- | --- |
| [CVE-2026-105924](https://www.qt.io/blog/security-advisory-cve-2026-105924) | QtCore 6.12.0; conversão de CBOR não confiável para JSON pode encerrar o processo; CVSS 4.0: 4,3 | QtCore distribuído. Nenhum uso de QCborValue/conversão correspondente identificado. Correção indicada em Qt 6.12.1 ou patch oficial; release bloqueada até correção/revalidação |
| [CVE-2026-116337](https://www.qt.io/blog/security-issue-cve-2026-116337?hsLang=en) | QtNetwork: consumo de recursos em resposta HTTP; solução indica Qt 6.12.1 ou patch | Biblioteca presente na instalação Qt, mas removida do candidato; nenhuma chamada QtNetwork na aplicação. O texto upstream tem redação ambígua no limite da faixa; não inferir que 6.12.1 é vulnerável contra a seção de solução |
| [CVE-2026-114366](https://www.qt.io/blog/security-issue-cve-2026-114366?hsLang=en) | QtWebSockets 6.12.0: possível exposição de credenciais | Módulo não importado nem biblioteca distribuída no candidato |
| [CVE-2026-110944](https://www.qt.io/blog/security-advisory-cve-2026-110944) | QtHttpServer 6.12.0: exaustão de memória | Módulo não importado nem biblioteca distribuída no candidato |
| [CVE-2026-111487](https://lists.qt-project.org/pipermail/announce/2026-November/000677.html) | Qt3D/assimp 6.12.0: escrita fora dos limites ao importar modelo | Componente não usado nem distribuído no candidato |
| [CVE-2026-100140](https://www.qt.io/blog/security-advisory-cve-2026-100140) | Qt5Compat 6.12.0: overflow em parser XML | Componente não usado nem distribuído no candidato |
| [GHSA-9fxf-4qw3-ghmr](https://github.com/pyinstaller/pyinstaller/security/advisories/GHSA-9fxf-4qw3-ghmr) | PyInstaller anterior a 6.22.1: elevação local de privilégio em executáveis privilegiados | Versão 6.22.3 fora da faixa afetada; executar o aplicativo como usuário comum |

A consulta ao [PyPI de PySide6](https://pypi.org/project/PySide6/) não identificou wheel estável posterior ao 6.12.0 nesta revisão. Não foi feita troca de versão nem substituição manual de uma biblioteca Qt: o conjunto PySide6/Shiboken/Qt deve permanecer compatível com Python 3.15. Quando houver distribuição corrigida, atualizar o conjunto e o lock, repetir auditoria, testes, build e validação nativa. Aplicar patch upstream exigiria reconstrução e rastreamento dos binários Qt; baixar um `.diff` não corrige a wheel instalada.

## Métodos e evidências

Executados na raiz do repositório; a consulta de rede inicialmente falhou por DNS no sandbox e foi repetida com acesso autorizado. `uv audit` e seu formato JSON são experimentais na versão usada.

```sh
.venv/bin/python tools/dependency_inventory.py --output security/reports/2026-11-09/inventory.json
uv --cache-dir /tmp/true-screen-uv-cache audit --locked --output-format json > /tmp/true-screen-audit-linux.json
.venv/bin/python tools/audit_pypi.py --tool uv==0.13.7 --tool uv-build==0.13.7 --output security/reports/2026-11-09/pypi.json
.venv/bin/python tools/bundle_inventory.py dist/linux-verified-candidate/true-screen --output security/reports/2026-11-09/bundle.json
.venv/bin/python tools/smoke_bundle.py dist/linux-verified-candidate/true-screen/true-screen --output security/reports/2026-11-09/smoke.json
```

Evidências preservadas: [inventário](../../security/reports/2026-11-09/inventory.json), [resposta OSV/uv](../../security/reports/2026-11-09/osv-uv-audit.json), [respostas PyPI](../../security/reports/2026-11-09/pypi.json), [manifesto do candidato](../../security/reports/2026-11-09/bundle.json) e [inicialização](../../security/reports/2026-11-09/smoke.json). Novas consultas devem usar outra pasta datada para preservar a evidência anterior. PyPI pode compartilhar fontes de advisories com OSV; os dois resultados não são provas independentes de segurança.

O candidato final possui 160.885.837 bytes em arquivos regulares, nove bibliotecas Qt nativas, nenhum symlink quebrado e nenhuma dependência ELF Qt sem fornecedor no diretório. QtNetwork, WebEngine, PDF, QML/Quick, Qt3D, HttpServer e WebSockets não aparecem como bibliotecas nativas coletadas. SVG/OpenGL e integrações XCB/Wayland são dependências dos plugins desktop; a presença de QtSvg não adiciona SVG aos formatos aceitos pelo aplicativo.

## Limites e pendências

- OSV/PyPI por pacote Python não inventariam automaticamente vulnerabilidades de código C/C++ embutido, codecs estáticos e bibliotecas do sistema. O manifesto ELF registra arquivos, hashes e SONAMEs, mas não é scanner de CVEs nem SBOM completo.
- Não foi encontrado SBOM ou conjunto completo de avisos/licenças nativas nas wheels inspecionadas. Identificar versões e patches de ICU, codecs PNG/JPEG, zlib, FreeType, OpenSSL e demais bibliotecas efetivamente incluídas antes da distribuição. Não concluir vulnerabilidade nem correção apenas pelo nome de SONAME; patches de distribuição podem manter a versão.
- A segurança do CPython embutido e dos pacotes nativos Fedora coletados precisa de auditoria própria com fontes/erratas da distribuição e versões exatas. Não foi executado scanner completo da cadeia nativa nem da imagem do sistema.
- O candidato local exige símbolos glibc 2.44. Isso impede considerá-lo compatível com a matriz Ubuntu prevista; construir no ambiente mínimo pretendido e repetir inspeção/testes.
- Faltam completar avisos/licenças/fontes correspondentes e homologar pacote em máquina limpa, captura, DPI e clipboard por sessão. Ver [procedimento de empacotamento](empacotamento-linux.md).

W11.1 conclui a pesquisa e o registro desta revisão. W11.3 permanece pendente: correção comprovada do Qt distribuído, análise nativa/licenças, baseline de build e homologação. Nenhum artefato foi publicado.
