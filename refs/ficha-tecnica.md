# Especificação técnica — Evidence Capture MVP

Rust + Slint

Windows / Linux · Desktop · Offline

## 1. Objetivo e escopo

Desenvolver uma aplicação desktop multiplataforma para produção de evidências técnicas, permitindo selecionar regiões de uma captura de tela, ampliá-las individualmente e posicioná-las sobre a imagem original ou fora dela.

O requisito central é preservar a resolução, a escala e o conteúdo da captura original, enquanto as regiões ampliadas permanecem editáveis e independentes.

A aplicação deverá funcionar sem serviços externos, banco de dados, privilégios administrativos ou dependência de runtimes adicionais.

### Escopo funcional do MVP

| Funcionalidade                           | MVP             |
| ---------------------------------------- | --------------- |
| Importar PNG/JPEG                        | Sim             |
| Colar imagem do clipboard                | Sim             |
| Selecionar região retangular             | Sim             |
| Zoom sobreposto                          | Sim             |
| Zoom externo                             | Sim             |
| Alternar modos de zoom                   | Sim             |
| Mover e redimensionar ampliação          | Sim             |
| Configurar fator de ampliação            | Sim             |
| Múltiplas ampliações                     | Sim             |
| Conector visual entre origem e ampliação | Sim             |
| Exportar PNG sem perdas                  | Sim             |
| Desfazer/refazer                         | Sim             |
| Salvar projeto editável                  | Sim             |
| Captura nativa da tela                   | Segunda entrega |
| OCR e reconstrução textual               | Fora do MVP     |
| Exportação PDF                           | Segunda entrega |

Decisão arquitetural: o editor será desenvolvido primeiro, desacoplado da captura nativa. Assim, a lógica principal poderá ser testada independentemente do sistema operacional.

## 2. Modelo visual e interação

Protótipo conceitual — dois modos de ampliação

Zoom externoZoom sobreposto

Protótipo interativo de comportamento, não uma renderização final da interface Slint. No modo externo, o canvas cresce para acomodar a ampliação; no sobreposto, a ampliação pode cobrir parte da captura.

### Comportamento de cada modo

Zoom sobreposto (`Overlay`)

A região ampliada é uma camada flutuante sobre a captura. Pode ser movida, redimensionada e colocada em qualquer posição. A captura original não é modificada.

Zoom externo (`External`)

A região ampliada é posicionada fora dos limites da captura, em uma área adicional do canvas. O sistema calcula o tamanho necessário para exportação, preservando a imagem original em sua escala nativa.

A alternância entre os modos não deve recriar a ampliação nem perder suas configurações.

## 3. Arquitetura de software

Adotaria um monólito modular com Cargo Workspace, separando o domínio, o processamento de imagem, a interface e os adaptadores de plataforma.

Presentation Layer

Slint · Eventos de mouse · Toolbar · Canvas · Painel de propriedades

Application Layer

Comandos · Undo/Redo · Gerenciamento de projetos · Exportação

Domain Layer

EvidenceProject · ZoomRegion · Geometry · Layer · Document

Image Engine

Crop · Resampling · Composition · PNG

Platform Adapters

Windows · Linux · Clipboard · Filesystem

### Dependências propostas

| Componente              | Tecnologia                |
| ----------------------- | ------------------------- |
| Linguagem               | Rust, edição 2024         |
| Interface               | Slint                     |
| Processamento de imagem | `image`                   |
| Serialização            | `serde`, `serde_json`     |
| Identificadores         | `uuid`                    |
| Erros                   | `thiserror`               |
| Logging                 | `tracing`                 |
| Hash de integridade     | `sha2`                    |
| Diálogos de arquivo     | `rfd`                     |
| Clipboard               | `arboard`                 |
| Testes de imagem        | Rust tests + fixtures PNG |

Não introduziria Tokio, ECS, GPU compute ou arquitetura de plugins no MVP. São complexidades que ainda não têm justificativa funcional.

## 4. Modelo de dados

O projeto deve ser persistido como um documento editável, não apenas como uma imagem renderizada.

A representação utiliza coordenadas em pixels da imagem original e coordenadas independentes no canvas.

### Entidades principais

```
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ZoomMode {
    Overlay,
    External,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum Resampling {
    Nearest,
    Bilinear,
    Bicubic,
    Lanczos3,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZoomRegion {
    pub id: Uuid,

    // Coordenadas relativas à imagem original.
    pub source: Rect,

    // Coordenadas no canvas de composição.
    pub destination: Rect,

    pub mode: ZoomMode,
    pub resampling: Resampling,
    pub z_index: i32,
    pub show_connector: bool,
    pub show_border: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvidenceProject {
    pub schema_version: u32,
    pub id: Uuid,
    pub image_path: String,
    pub image_sha256: String,
    pub zoom_regions: Vec<ZoomRegion>,
}
```

### Decisões de modelagem

1\. Source e destination são independentes. A região original permanece fixa, enquanto a ampliação pode ser reposicionada sem modificar a seleção.

2\. Zoom não é um atributo obrigatório separado. O fator efetivo é calculado pelas dimensões de origem e destino. Isso permite ampliações não uniformes, embora o editor deva preservar a proporção por padrão.

3\. `z_index` define a ordem de composição. Duas ampliações podem se sobrepor sem alterar a imagem base.

4\. O arquivo original é imutável. O hash SHA-256 permite verificar se a imagem-fonte foi alterada.

5\. `schema_version` permite migração futura. O formato poderá evoluir sem invalidar os projetos existentes.

O `image_path` acima é uma simplificação inicial. Para projetos portáteis, adotaria um pacote `.evidence` contendo um manifesto JSON e a imagem original, com caminhos internos relativos.

### Exemplo de documento persistido

```
{
  "schema_version": 1,
  "id": "82f5364a-3490-48b6-94ef-451d3ebd829c",
  "image_path": "assets/original.png",
  "image_sha256": "<sha256-da-imagem>",
  "zoom_regions": [
    {
      "id": "16cc7f20-97c4-4804-bf31-c7a32e03d349",
      "source": {
        "x": 420,
        "y": 180,
        "width": 300,
        "height": 80
      },
      "destination": {
        "x": 1940,
        "y": 220,
        "width": 600,
        "height": 160
      },
      "mode": "External",
      "resampling": "Lanczos3",
      "z_index": 1,
      "show_connector": true,
      "show_border": true
    }
  ]
}
```

A validação do domínio deve rejeitar coordenadas não finitas, dimensões nulas ou negativas, seleções fora da imagem e ampliações que excedam os limites configurados de memória.

## 5. Motor de imagem

A implementação deve utilizar duas representações distintas:

- Imagem-fonte: bitmap original, mantido em memória sem modificações.
- Cena editável: coleção de objetos geométricos que referenciam regiões da imagem-fonte.

A exportação executa a composição somente quando solicitada. Isso evita degradação cumulativa por múltiplas operações de zoom.

### Pipeline de renderização

\#chatgpt-mermaid-\_r_l2\_{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,Segoe UI,Helvetica,Apple Color Emoji,Arial,sans-serif,Segoe UI Emoji,Segoe UI Symbol;font-size:16px;fill:rgb(237, 237, 237);}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#chatgpt-mermaid-\_r_l2\_ .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_l2\_ .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#chatgpt-mermaid-\_r_l2\_ .error-icon{fill:rgb(48, 48, 48);}#chatgpt-mermaid-\_r_l2\_ .error-text{fill:rgb(237, 237, 237);stroke:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ .edge-thickness-normal{stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .edge-thickness-thick{stroke-width:3.5px;}#chatgpt-mermaid-\_r_l2\_ .edge-pattern-solid{stroke-dasharray:0;}#chatgpt-mermaid-\_r_l2\_ .edge-thickness-invisible{stroke-width:0;fill:none;}#chatgpt-mermaid-\_r_l2\_ .edge-pattern-dashed{stroke-dasharray:3;}#chatgpt-mermaid-\_r_l2\_ .edge-pattern-dotted{stroke-dasharray:2;}#chatgpt-mermaid-\_r_l2\_ .marker{fill:rgb(175, 175, 175);stroke:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_l2\_ .marker.cross{stroke:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_l2\_ svg{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,Segoe UI,Helvetica,Apple Color Emoji,Arial,sans-serif,Segoe UI Emoji,Segoe UI Symbol;font-size:16px;}#chatgpt-mermaid-\_r_l2\_ p{margin:0;}#chatgpt-mermaid-\_r_l2\_ .label{font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,Segoe UI,Helvetica,Apple Color Emoji,Arial,sans-serif,Segoe UI Emoji,Segoe UI Symbol;color:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ .cluster-label text{fill:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ .cluster-label span{color:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ .cluster-label span p{background-color:transparent;}#chatgpt-mermaid-\_r_l2\_ .label text,#chatgpt-mermaid-\_r_l2\_ span{fill:rgb(237, 237, 237);color:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ .node rect,#chatgpt-mermaid-\_r_l2\_ .node circle,#chatgpt-mermaid-\_r_l2\_ .node ellipse,#chatgpt-mermaid-\_r_l2\_ .node polygon,#chatgpt-mermaid-\_r_l2\_ .node path{fill:rgb(9, 23, 44);stroke:rgb(31, 78, 148);stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .rough-node .label text,#chatgpt-mermaid-\_r_l2\_ .node .label text,#chatgpt-mermaid-\_r_l2\_ .image-shape .label,#chatgpt-mermaid-\_r_l2\_ .icon-shape .label{text-anchor:middle;}#chatgpt-mermaid-\_r_l2\_ .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .rough-node .label,#chatgpt-mermaid-\_r_l2\_ .node .label,#chatgpt-mermaid-\_r_l2\_ .image-shape .label,#chatgpt-mermaid-\_r_l2\_ .icon-shape .label{text-align:center;}#chatgpt-mermaid-\_r_l2\_ .node.clickable{cursor:pointer;}#chatgpt-mermaid-\_r_l2\_ .root .anchor path{fill:rgb(175, 175, 175)!important;stroke-width:0;stroke:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_l2\_ .arrowheadPath{fill:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_l2\_ .edgePath .path{stroke:rgb(175, 175, 175);stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .flowchart-link{stroke:rgb(175, 175, 175);fill:none;}#chatgpt-mermaid-\_r_l2\_ .edgeLabel{background-color:rgb(0, 0, 0);text-align:center;}#chatgpt-mermaid-\_r_l2\_ .edgeLabel p{background-color:rgb(0, 0, 0);}#chatgpt-mermaid-\_r_l2\_ .edgeLabel rect{opacity:0.5;background-color:rgb(0, 0, 0);fill:rgb(0, 0, 0);}#chatgpt-mermaid-\_r_l2\_ .labelBkg{background-color:rgba(0, 0, 0, 0.5);}#chatgpt-mermaid-\_r_l2\_ .cluster rect{fill:rgb(48, 48, 48);stroke:rgba(255, 255, 255, 0.15);stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .cluster text{fill:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ .cluster span{color:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,Segoe UI,Helvetica,Apple Color Emoji,Arial,sans-serif,Segoe UI Emoji,Segoe UI Symbol;font-size:12px;background:rgb(48, 48, 48);border:1px solid rgba(255, 255, 255, 0.15);border-radius:2px;pointer-events:none;z-index:100;}#chatgpt-mermaid-\_r_l2\_ .flowchartTitleText{text-anchor:middle;font-size:18px;fill:rgb(237, 237, 237);}#chatgpt-mermaid-\_r_l2\_ rect.text{fill:none;stroke-width:0;}#chatgpt-mermaid-\_r_l2\_ .icon-shape,#chatgpt-mermaid-\_r_l2\_ .image-shape{background-color:rgb(0, 0, 0);text-align:center;}#chatgpt-mermaid-\_r_l2\_ .icon-shape p,#chatgpt-mermaid-\_r_l2\_ .image-shape p{background-color:rgb(0, 0, 0);padding:2px;}#chatgpt-mermaid-\_r_l2\_ .icon-shape .label rect,#chatgpt-mermaid-\_r_l2\_ .image-shape .label rect{opacity:0.5;background-color:rgb(0, 0, 0);fill:rgb(0, 0, 0);}#chatgpt-mermaid-\_r_l2\_ .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#chatgpt-mermaid-\_r_l2\_ .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#chatgpt-mermaid-\_r_l2\_ .node .neo-node{stroke:rgb(31, 78, 148);}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node rect,#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].cluster rect,#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node polygon{stroke:url(#chatgpt-mermaid-\_r_l2\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].swimlane.cluster rect{filter:none;}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node path{stroke:url(#chatgpt-mermaid-\_r_l2\_-gradient);stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node .neo-line path{stroke:rgb(31, 78, 148);filter:none;}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node circle{stroke:url(#chatgpt-mermaid-\_r_l2\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].node circle .state-start{fill:#000000;}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].icon-shape .icon{fill:url(#chatgpt-mermaid-\_r_l2\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_l2\_ [data-look="neo"].icon-shape .icon-neo path{stroke:url(#chatgpt-mermaid-\_r_l2\_-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#chatgpt-mermaid-\_r_l2\_ .node text{font-size:14px;font-weight:600;letter-spacing:normal;fill:rgb(153, 206, 255);}#chatgpt-mermaid-\_r_l2\_ .edgeLabels text{font-size:13px;font-weight:600;letter-spacing:-0.08px;fill:rgb(153, 206, 255);}#chatgpt-mermaid-\_r_l2\_ .node tspan[font-weight="normal"],#chatgpt-mermaid-\_r_l2\_ .edgeLabels tspan[font-weight="normal"]{font-weight:600;}#chatgpt-mermaid-\_r_l2\_ .edgeLabel .label rect{opacity:1;rx:13px;ry:13px;fill:rgb(0, 14, 26);stroke:rgb(26, 62, 95);stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .node rect,#chatgpt-mermaid-\_r_l2\_ .node circle,#chatgpt-mermaid-\_r_l2\_ .node ellipse,#chatgpt-mermaid-\_r_l2\_ .node polygon,#chatgpt-mermaid-\_r_l2\_ .node path{fill:rgb(0, 40, 77);stroke:rgba(255, 255, 255, 0.1);stroke-width:1px;}#chatgpt-mermaid-\_r_l2\_ .node rect{rx:16px;ry:16px;}#chatgpt-mermaid-\_r_l2\_ .mermaid-decision .label-container{fill:rgb(0, 14, 26);stroke:rgb(26, 62, 95);stroke-dasharray:2px,2px;}#chatgpt-mermaid-\_r_l2\_ .edgePaths .flowchart-link{stroke:rgb(175, 175, 175);stroke-width:1px;stroke-linecap:round;stroke-linejoin:round;}#chatgpt-mermaid-\_r_l2\_ .marker{fill:rgb(175, 175, 175);stroke:rgb(175, 175, 175);}#chatgpt-mermaid-\_r_l2\_ :root{--mermaid-font-family:-apple-system-body,ui-sans-serif,-apple-system,system-ui,Segoe UI,Helvetica,Apple Color Emoji,Arial,sans-serif,Segoe UI Emoji,Segoe UI Symbol;}Imagem originalValidar regiõesCalcular limites do canvasCriar superfície de saídaDesenhar imagem originalRecortar região na fonteRedimensionar cominterpolaçãoCompor ampliação nodestinoDesenhar bordas econectoresOutras ampliações?Exportar PNG sem perdasSimNão

### Algoritmo de composição

```
use image::{
    imageops::{self, FilterType},
    RgbaImage,
};

pub fn render_zoom(
    source: &RgbaImage,
    canvas: &mut RgbaImage,
    src: (u32, u32, u32, u32),
    dst: (i64, i64, u32, u32),
) {
    let (sx, sy, sw, sh) = src;
    let (dx, dy, dw, dh) = dst;

    let crop = imageops::crop_imm(
        source, sx, sy, sw, sh
    ).to_image();

    let resized = imageops::resize(
        &crop,
        dw,
        dh,
        FilterType::Lanczos3,
    );

    imageops::overlay(canvas, &resized, dx, dy);
}
```

Esse código representa apenas a operação central. A implementação definitiva deverá validar os limites antes do recorte, converter coordenadas com segurança e controlar o consumo de memória.

### Estratégias de legibilidade

| Estratégia          | Aplicação                                                         |
| ------------------- | ----------------------------------------------------------------- |
| Nearest Neighbor    | Pixel art e capturas com pixels que precisam permanecer distintos |
| Bicubic             | Texto e interfaces com suavização moderada                        |
| Lanczos3            | Padrão inicial para ampliação de interfaces                       |
| Contraste e nitidez | Opcional, com indicação de imagem processada                      |

O objetivo não é fabricar detalhes, mas maximizar a legibilidade dos pixels disponíveis.

## 6. Componentes Slint

A interface será organizada em componentes reutilizáveis.

Wireframe de referência: barra de ferramentas à esquerda, área de edição central e propriedades da ampliação selecionada à direita.

### Árvore de componentes

```
MainWindow
├── MenuBar
├── ToolBar
│   ├── SelectionTool
│   ├── ZoomTool
│   ├── PanTool
│   └── ExportAction
├── Workspace
│   ├── CanvasViewport
│   │   ├── BackgroundImage
│   │   ├── SourceSelection
│   │   ├── ZoomLayer
│   │   ├── ConnectorLayer
│   │   └── SelectionHandles
│   └── PropertiesPanel
│       ├── ZoomModeSelector
│       ├── ScaleControl
│       ├── ResamplingSelector
│       └── BorderConnectorOptions
└── StatusBar
```

### Responsabilidades

CanvasViewport: conversão entre coordenadas da tela e do documento, pan, zoom de navegação e encaminhamento dos eventos de mouse.

SourceSelection: criação e edição de retângulos na imagem original.

ZoomLayer: apresentação das regiões ampliadas, com movimentação e redimensionamento.

PropertiesPanel: alteração de propriedades do objeto selecionado, incluindo a troca entre `Overlay` e `External`.

Application Controller: recebe os comandos da interface, modifica o modelo de domínio e atualiza a cena.

Um detalhe importante: zoom do editor e zoom da evidência são operações diferentes. O zoom do editor modifica apenas a visualização do canvas; o zoom da evidência altera o tamanho da região ampliada no documento exportado.

Para a primeira versão, usaria os eventos de ponteiro do Slint e uma composição de preview em resolução reduzida quando necessário. A renderização de exportação continuaria operando na resolução original.

## 7. Estrutura do repositório

Para o MVP, reduziria a quantidade de crates para evitar modularização excessiva.

```
evidence-capture/
├── Cargo.toml
├── Cargo.lock
├── app/
│   ├── Cargo.toml
│   ├── build.rs
│   ├── src/
│   │   ├── main.rs
│   │   ├── controller.rs
│   │   └── view_model.rs
│   └── ui/
│       ├── main.slint
│       ├── canvas.slint
│       ├── toolbar.slint
│       └── properties.slint
├── crates/
│   ├── evidence-core/
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── geometry.rs
│   │       ├── project.rs
│   │       ├── zoom.rs
│   │       └── commands.rs
│   ├── evidence-image/
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── renderer.rs
│   │       ├── resampling.rs
│   │       └── exporter.rs
│   └── evidence-platform/
│       └── src/
│           ├── lib.rs
│           ├── clipboard.rs
│           └── dialogs.rs
├── tests/
│   └── fixtures/
└── .github/
    └── workflows/
        └── build.yml
```

O crate `evidence-platform` concentra as diferenças entre sistemas operacionais. Quando a captura nativa for implementada, poderá receber adaptadores específicos de Windows e Linux sem modificar o domínio.

## 8. Plano de implementação

Roadmap do MVP

Estimativa: 40–60 horas

Estimativa preliminar para desenvolvimento individual com familiaridade em Rust e Slint; não inclui OCR ou captura nativa.

1Fundação e domínio5–7 h

Criar Cargo Workspace e aplicação Slint

Implementar geometria, projeto e regiões

Criar testes de invariantes e serialização

2Motor de composição8–12 h

3Editor interativo14–20 h

4Persistência e histórico6–9 h

5Testes e distribuição7–12 h

## 9. Critérios de aceitação

O MVP será considerado concluído quando passar nos seguintes cenários:

| Cenário               | Resultado esperado                               |
| --------------------- | ------------------------------------------------ |
| Captura 1920 × 1080   | Imagem original sem alteração de pixels          |
| Zoom 200%             | Recorte ampliado com dimensões 2×                |
| Zoom externo          | Canvas expandido sem reduzir a imagem original   |
| Zoom sobreposto       | Ampliação renderizada como camada independente   |
| Alternar modos        | Região e propriedades preservadas                |
| Três ampliações       | Composição correta e ordem de camadas respeitada |
| Salvar e reabrir      | Todas as regiões recuperadas                     |
| Undo/Redo             | Estado anterior restaurado corretamente          |
| Exportar PNG          | Resultado sem perdas adicionais de compressão    |
| Windows 125%/150% DPI | Coordenadas de seleção corretas                  |
| Linux Wayland         | Editor funcional com importação de imagens       |

Para garantir confiabilidade, incluiria testes automatizados de composição com golden images, além de testes de geometria para seleções próximas das bordas e canvas com coordenadas negativas.

A validação visual deverá comparar o resultado exportado com imagens de referência, respeitando diferenças deliberadas de interpolação.

## 10. Decisões arquiteturais finais

| Decisão                                  | Justificativa                                                  |
| ---------------------------------------- | -------------------------------------------------------------- |
| Rust + Slint                             | Binário nativo e interface multiplataforma                     |
| Monólito modular                         | Simplicidade de desenvolvimento e manutenção                   |
| Editor desacoplado da captura            | Permite validar a funcionalidade principal primeiro            |
| Documento não destrutivo                 | Preserva integridade e permite edição posterior                |
| Renderização sob demanda                 | Evita degradação acumulada                                     |
| Zoom externo e sobreposto                | Atende diferentes tipos de evidência                           |
| Processamento local                      | Não exige envio de evidências corporativas a serviços externos |
| PNG como formato inicial                 | Compressão sem perdas                                          |
| Windows como alvo principal de validação | Compatibilidade com o ambiente corporativo                     |

### Primeiro incremento recomendado

Começaria implementando uma aplicação que abre um PNG e permite selecionar um retângulo, gerar uma ampliação externa de 200% e exportar o resultado.

Esse incremento valida os três pontos de maior risco técnico: mapeamento de coordenadas, composição da imagem e legibilidade do recorte ampliado.

Depois disso, adicionaria o modo sobreposto, os controles de edição, persistência e integração com clipboard.

Não começaria pela captura nativa, porque ela introduz particularidades do Windows e Linux antes de validarmos o motor de evidências.

Resultado esperado: um executável desktop que produz evidências legíveis, preserva a imagem original e oferece edição não destrutiva, sem depender de qualquer serviço externo.