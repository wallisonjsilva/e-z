# AGENTS.md — True Screen

## Objetivo e fontes

Criar aplicativo desktop offline de screenshot e ampliação de evidências, com implementação e validação Linux primeiro e port Windows posterior. Responder e documentar em português.

Leia [especificação](specs/true-screen.md), [design](specs/designs/true-screen.md), [TASKS.md](TASKS.md) e [STATE.md](STATE.md) antes de implementar. Consulte `refs/` como contexto histórico. Conflitos entre referências foram resolvidos na especificação; não misture Python/Qt e Rust/Slint.

## Fluxo obrigatório SDD

1. Specify: registrar requisitos e critérios verificáveis em `specs/`.
2. Design: validar arquitetura contra requisitos em `specs/designs/`.
3. Tasks: decompor em tarefas pequenas e verificáveis no `TASKS.md`.
4. Execute: executar a tarefa atual, verificar resultados e atualizar estado.

Use `[ ]` pendente, `[/]` em andamento e `[x]` concluído. Não marque implementação concluída por existir documentação. Em falha, registrar causa e ajuste no planejamento antes da correção; atualizar especificação apenas se o comportamento precisar mudar. Trabalhar dentro do escopo autorizado, sem exigir aprovação adicional para escolhas rotineiras.

## Regras de implementação

- Python + PySide6, seguindo `src/true_screen`; confirmar suporte do Python antes de fixar dependências.
- Preservar base imutável e gerar cada ampliação diretamente dela.
- Separar zoom de navegação, pixels físicos e coordenadas lógicas/DPI.
- Centralizar composição para exportação e clipboard; excluir elementos de edição.
- Isolar captura/clipboard/diálogos da lógica do documento. Nenhuma dependência Windows no domínio.
- Implementar e homologar E1 e E2 no Linux antes do port Windows em E3. Validar X11 e Wayland; Wayland usa portal e permissões. Manter o núcleo compartilhado e adaptar apenas integrações de plataforma no port.
- Não introduzir runtime assíncrono, banco, rede, plugins ou migração de stack sem requisito documentado.
- Validar limites antes de alocar, carregar ou extrair dados. Não registrar conteúdo sensível.
- Preservar alterações existentes do usuário e arquivos de referência.

## Qualidade e entrega

Testar invariantes de geometria e composição, persistência e histórico quando implementados. Captura, DPI, clipboard e distribuição exigem testes nativos. Registrar testes executados e limitações; compilação ou mock não comprovam compatibilidade Windows/Linux.

As dependências e ferramentas de teste ainda serão configuradas. Após configurá-las, registrar comandos reproduzíveis em README e STATE. Não afirmar que testes passaram sem executá-los.

## Documentação e memória

`STATE.md` contém objetivo atual, decisões, bloqueios e próximos passos. `TASKS.md` controla execução e dependências.

SDD, design, estado e instruções usam Markdown `.md`, conforme as fases do template. As regras MDX do template aplicam-se aos futuros manuais e release notes para usuários em `docs/content/`, não aos documentos de engenharia. Criar templates e TOC quando esses guias forem introduzidos; não referenciar arquivos inexistentes como se disponíveis.

Manuais devem usar linguagem simples, voz ativa, passos orientados a tarefas, campos em **negrito** e exemplos fictícios. Não publicar imagens reais, credenciais ou dados pessoais. Documentação técnica pode detalhar arquitetura e contratos necessários à implementação.
