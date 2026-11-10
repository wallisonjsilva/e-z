Para colocar esse MVP em funcionamento rapidamente, eu recomendo Python + PySide6 (Qt) + MSS + Pillow.

É uma combinação que permite desenvolver a captura, a interface gráfica e o processamento de imagens sem precisar implementar componentes de baixo nível.

Como a prioridade é Windows, mas você também quer Linux, manteria uma única base de código.

## Stack recomendada

| Componente        | Tecnologia                     | Responsabilidade                      |
| ----------------- | ------------------------------ | ------------------------------------- |
| Interface gráfica | PySide6                        | Janela, canvas, seleção e manipulação |
| Captura de tela   | MSS                            | Captura de monitores e regiões        |
| Edição interativa | QGraphicsScene / QGraphicsView | Zoom, movimentação e sobreposição     |
| Processamento     | Pillow                         | Recorte, Lanczos, exportação          |
| Atalhos globais   | keyboard ou pynput             | Acionar captura fora do aplicativo    |
| Empacotamento     | PyInstaller                    | Gerar `.exe` para Windows             |

Uma otimização: o próprio Qt já oferece `QScreen.grabWindow()` e `QImage`, `QPixmap` e `QPainter`. Portanto, podemos começar somente com PySide6 e adicionar MSS ou Pillow se houver necessidade. Menos dependências significam menos problemas de distribuição.

No Linux com Wayland, a captura direta por MSS ou Qt pode ser limitada. Para essa plataforma, utilizaria o XDG Desktop Portal ou integração com o Spectacle.

## Como seria o MVP

Fluxo de utilização

1\. Capturar tela

Botão ou atalho para capturar o monitor

2\. Selecionar região

Arrastar o mouse sobre o texto pequeno

3\. Ampliar

Zoom 150%, 200%, 300% ou personalizado

4\. Posicionar

Sobrepor à captura ou posicionar externamente

5\. Exportar

Salvar PNG ou copiar resultado para o Word

## Estimativa de implementação

MVP funcional

# 6–10 horas

Estimativa

Considerando desenvolvimento assistido por IA, Windows como primeira plataforma e sem OCR, persistência de projetos ou instalador sofisticado.

| Etapa                             | Tempo estimado |
| --------------------------------- | -------------- |
| Interface Qt + captura do monitor | 1–2 h          |
| Seleção de região                 | 1–2 h          |
| Zoom externo e sobreposto         | 2–3 h          |
| Arrastar ampliação e exportar PNG | 1–2 h          |
| Empacotar e testar no Windows     | 1 h            |

O suporte Linux, especialmente Wayland, exigirá validação adicional.

## Minha escolha para acelerar ainda mais

Eu utilizaria exclusivamente PySide6 na primeira implementação, porque o Qt já fornece praticamente tudo que precisamos:

- `QScreen.grabWindow()` para captura inicial.
- `QGraphicsView` para visualização e interação.
- `QGraphicsPixmapItem` para a imagem original e as ampliações.
- `QGraphicsRectItem` para seleção de regiões.
- `QPainter` para composição e exportação.
- `QClipboard` para copiar o resultado diretamente.

O uso de `QGraphicsScene` é particularmente interessante: o zoom externo pode ser colocado fora dos limites da imagem original, enquanto o zoom sobreposto permanece dentro deles. A própria cena calcula os limites de seus elementos, simplificando a exportação.

Atenção: para capturar janelas minimizadas, telas protegidas ou conteúdo acelerado por hardware, a API simples do Qt pode apresentar limitações. No Windows, se necessário, podemos integrar Windows Graphics Capture posteriormente.

### Recomendação de execução

Eu começaria com um único projeto Python, sem arquitetura multicamadas e sem múltiplos pacotes:

```
evidence-capture/
├── main.py
├── requirements.txt
└── assets/
```

Quando a ferramenta estiver validada no uso real, podemos refatorar os componentes e avaliar a migração para Rust.

O que eu faria agora: implementar diretamente a primeira versão com captura Windows, seleção retangular, zoom sobreposto/externo, movimentação do recorte e exportação PNG. Essa versão já resolve a necessidade principal de produzir evidências legíveis, sem gastar tempo construindo infraestrutura que ainda não é necessária.