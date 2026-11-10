# Auditoria de dependências e empacotamento Linux

## Escopo autorizado

Pesquisar as bibliotecas usadas, verificar vulnerabilidades conhecidas e documentar empacotamento reproduzível, mantendo Linux como alvo inicial e Windows posterior. Não confundir auditoria Python com análise de Qt/codecs nativos nem build local com homologação.

## Requisitos e aceitação

- Inventariar versões do lockfile, ambiente, ferramentas de build e módulos Qt usados; distinguir dependência instalada de componente realmente incluído no pacote.
- Executar consulta de vulnerabilidades por nome/versão em serviço público e revisar avisos oficiais Qt/PyInstaller. Enviar somente metadados públicos de dependências, sem imagens, código, caminhos ou credenciais.
- Registrar data, comandos, evidências, IDs/faixas afetadas, aplicabilidade e limitações. Consulta incompleta não permite concluir ausência de vulnerabilidades.
- Documentar build Linux em diretório com PyInstaller, plataforma mínima, dependências externas, licenças, integridade, verificações e rollback. Excluir módulos não usados quando comprovado pelo inventário do artefato.
- Preparar e verificar uma receita concreta de build local quando o ambiente permitir, sem publicar release nem marcar E1 homologada sem matriz nativa.
- Vulnerabilidade confirmada no componente distribuído deve constar como bloqueio de release até correção/revalidação; correções rotineiras podem seguir o escopo autorizado, preservando referências e trabalho existente.

## Design e execução

Usar uv audit disponível no ambiente para OSV e fontes oficiais para componentes nativos. Conservar evidência estruturada e relatório técnico em Markdown. A análise do empacotamento deve partir do código/lock atuais e selecionar apenas QtCore, QtGui, QtWidgets e QtDBus, mais plugins necessários, sem coletar WebEngine/PDF indiscriminadamente. Decomposição em W11 no TASKS.md; resultados no STATE.md.
