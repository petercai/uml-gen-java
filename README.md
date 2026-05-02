# UML Gen for Source-to-UML CLI Workflows

UML Gen converts source code into PlantUML class and sequence diagrams from a command-line workflow.

Teams keep architecture artifacts in sync with implementation by generating diagrams directly from code and instruction. The workflow is scriptable for local development and CI pipelines. The output is optimized for review in UMLMark tools.

<p align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen" alt="Build passing">
  <img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-dual--license-orange" alt="Dual license model badge">
  <a href="https://github.com/petercai/uml-gen-java/stargazers"><img src="https://img.shields.io/github/stars/petercai/uml-gen-java?style=social" alt="GitHub stars for uml-gen-java"></a>
</p>

## Why UML Gen

Problem:

- Architecture diagrams become outdated when maintained manually.
- Large codebases are hard to inspect at class and interaction level.
- Teams need automation-friendly UML output for CI and review workflows.

Solution:

- Use `umlc-gen` and `umls-gen` to run configuration-driven generation pipelines.
- Use `umlc` and `umls` to generate class and sequence diagrams from UMLMark eclipse input.
- Produce PlantUML output that can be reviewed, versioned, and shared.
- Integrate generation commands into scripts and CI jobs with consistent inputs.

## Key Capabilities

- Instruction-driven class generation with `umlc-gen`.
- Instruction-driven sequence generation with `umls-gen`.
- Command-line class diagram generation with `umlc`.
- Command-line sequence diagram generation with `umls`.
- PlantUML output suitable for [UMLMark](https://github.com/petercai/vscode-umlmark) preview and navigation workflows.

## Supported File Types

- Source input: Java source files (`.java`) and source roots.
- Generation instruction: YAML (`.yaml`, `.yml`).
- Output: PlantUML (`.puml`, `.plantuml`) and rendered SVG from [UMLMark Tool](https://github.com/petercai/vscode-umlmark).

## Example
- PlantUML Class Diagram
  ![umlc-CategoryController](https://raw.githubusercontent.com/petercai/Vision/refs/heads/master/uml/umlc-CategoryController_Depth3.svg)
  <div align="center">

  <sub><em>Optimized for viewing with <a href="https://github.com/petercai/vscode-umlmark" target="_blank">vscode-umlmark</a></em></sub>

  </div>

  - PlantUML Source

    ```
    @startuml umlc-CategoryController_Depth3
    legend top center
      [[uml/umlc-CategoryController.yaml:1 ⚓uml/umlc-CategoryController.yaml]]
    end legend
    top to bottom direction
    hide empty members

    class VisionConfiguration [[src/main/java/cai/peter/vision/common/VisionConfiguration.java:21]] {
      + [[src/main/java/cai/peter/vision/common/VisionConfiguration.java:31 VisionConfiguration()]]
      + [[src/main/java/cai/peter/vision/common/VisionConfiguration.java:55 getVersion()]]
      + [[src/main/java/cai/peter/vision/common/VisionConfiguration.java:59 getGitCommit()]]
    }
    class AbstractFaviconFetcher [[src/main/java/cai/peter/vision/favicon/AbstractFaviconFetcher.java:13]] {
      + [[src/main/java/cai/peter/vision/favicon/AbstractFaviconFetcher.java:22 fetch()]]
      # [[src/main/java/cai/peter/vision/favicon/AbstractFaviconFetcher.java:24 isValidIconResponse()]]
    }
    class FeedQueues [[src/main/java/cai/peter/vision/feed/FeedQueues.java:23]] {
      + [[src/main/java/cai/peter/vision/feed/FeedQueues.java:39 take()]]
      + [[src/main/java/cai/peter/vision/feed/FeedQueues.java:52 add()]]
      + [[src/main/java/cai/peter/vision/feed/FeedQueues.java:115 giveBack()]]
      + [[src/main/java/cai/peter/vision/feed/FeedQueues.java:131 isAllDone()]]
    }
    ...

    AbstractFaviconFetcher --> Feed
    FeedQueues --> FeedsRepository
    FeedQueues --> FeedRefreshContext
    FeedQueues --> Feed
    FeedRefreshContext --> Feed
    FeedRefreshContext --> FeedEntry
    SubscriptionDAO --> UnreadCount
    Feed --|> AbstractModel
    ...
    @enduml
    ```

- PlantUML Sequence Diagram
  ![umls-FeedRefreshTaskGiver](https://raw.githubusercontent.com/petercai/Vision/refs/heads/master/uml/umls-FeedRefreshTaskGiver.svg)
  <div align="center">

  <sub><em>Optimized for viewing with <a href="https://github.com/petercai/vscode-umlmark" target="_blank">vscode-umlmark</a></em></sub>

  </div>

  - PlantUML Source

    ```
    @startuml umls-FeedRefreshTaskGiver
    legend top center
      [[uml/umls-FeedRefreshTaskGiver.yaml:1 ⚓uml/umls-FeedRefreshTaskGiver.yaml]]
    end legend
    hide footbox
    skinparam ParticipantPadding 20
    skinparam BoxPadding 10
    ' autoactivate on

    actor "Actor" as Actor_0
    participant "FeedRefreshTaskGiver:\nFeedRefreshTaskGiver" as FeedRefreshTaskGiver_1 [[src/main/java/cai/peter/vision/feed/FeedRefreshTaskGiver.java:9]]
    participant "FeedQueues:\nFeedQueues" as FeedQueues_2 [[src/main/java/cai/peter/vision/feed/FeedQueues.java:23]]
    participant "AdminApi:\nAdminApi" as AdminApi_3 [[src/main/generated/cai/peter/vision/api/controller/AdminApi.java:37]]
    participant "FeedRefreshWorker:\nFeedRefreshWorker" as FeedRefreshWorker_4 [[src/main/java/cai/peter/vision/feed/FeedRefreshWorker.java:25]]
    participant "FeedFetcher:\nFeedFetcher" as FeedFetcher_5 [[src/main/java/cai/peter/vision/feed/FeedFetcher.java:23]]
    participant "HttpGetter:\nHttpGetter" as HttpGetter_6 [[src/main/java/cai/peter/vision/feed/HttpGetter.java:47]]
    participant "FeedParser:\nFeedParser" as FeedParser_7 [[src/main/java/cai/peter/vision/feed/FeedParser.java:32]]
    ...
    Actor_0 -> FeedRefreshTaskGiver_1 : process()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedRefreshTaskGiver.java:30 FeedRefreshTaskGiver.java:30]]\ncaller:[entry include-order]
    FeedRefreshTaskGiver_1 -> FeedQueues_2 : take()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:39 FeedQueues.java:39]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedRefreshTaskGiver.java:34 FeedRefreshTaskGiver.java:34]]
    FeedQueues_2 -> FeedQueues_2 : refill()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:66 FeedQueues.java:66]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:43 FeedQueues.java:43]]
    FeedQueues_2 -> FeedQueues_2 : add()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:52 FeedQueues.java:52]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:74 FeedQueues.java:74]]
    FeedQueues_2 -> FeedQueues_2 : add()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:52 FeedQueues.java:52]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:58 FeedQueues.java:58]]
    FeedQueues_2 -> AdminApi_3 : save()\ncallee:[[src/main/generated/cai/peter/vision/api/controller/AdminApi.java:230 AdminApi.java:230]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedQueues.java:108 FeedQueues.java:108]]
    FeedRefreshTaskGiver_1 -> FeedRefreshWorker_4 : updateFeed()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedRefreshWorker.java:47 FeedRefreshWorker.java:47]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedRefreshTaskGiver.java:36 FeedRefreshTaskGiver.java:36]]
    FeedRefreshWorker_4 -> FeedRefreshWorker_4 : update()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedRefreshWorker.java:52 FeedRefreshWorker.java:52]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedRefreshWorker.java:49 FeedRefreshWorker.java:49]]
    FeedRefreshWorker_4 -> FeedFetcher_5 : fetch()\ncallee:[[src/main/java/cai/peter/vision/feed/FeedFetcher.java:32 FeedFetcher.java:32]]\ncaller:[[src/main/java/cai/peter/vision/feed/FeedRefreshWorker.java:58 FeedRefreshWorker.java:58]]
    ...
    @enduml
    ```


## Install

Install the UML Gen CLI:

```bash
pip install uml-gen
```

Or:

```bash
pipx install uml-gen
```

Install from source:

```bash
git clone https://github.com/petercai/uml-gen-java.git
cd uml-gen-java
uv pip install -e .
```

## Quick Start

1. Prepare a generation instruction in YAML.
2. Generate a class diagram with `umlc-gen --config instruction.yaml`.
3. Generate a sequence diagram with `umls-gen --config instruction.yaml`.
5. Open generated `.puml` files in [UMLMark](https://github.com/petercai/vscode-umlmark) for preview and source navigation.

## Developer Flow (UMLMark Suite)

Recommended end-to-end workflow for Design as Code / Architecture as Code:

1. Write or update source code.
2. Generate PlantUML diagrams from source using UML Gen (CLI).
3. Open generated `.puml` diagrams in [UMLMark](https://github.com/petercai/vscode-umlmark) preview.
4. Navigate from diagram elements back to source files.
5. Iterate: update source, regenerate diagrams, and re-verify in preview.

Flow summary:

`source code -> uml-gen generation -> .puml preview in UMLMark -> code navigation back -> iterate`

## Configuration Highlights

- Generate class diagram:
  ```bash
    # fine-grained diagram generation control
    umlc_gen.py --config <your-generation-instruction>.yaml 

    # quick generation
    umlc_gen.py --input src/main/java/com/example/MyService.java
    # or when the class name is unique
    umlc_gen.py --input MyService
  ```  
  <div align="right">

  <sub><em>refer to <a href="https://github.com/petercai/Vision/blob/master/uml/umlc-CategoryController.yaml" target="_blank">instruction example</a></em></sub>

  </div>

- Generate sequence diagram:
  ```bash
  umls_gen.py --config <your-generation-instruction>.yaml
  ```
  <div align="right">

  <sub><em>refer to <a href="https://github.com/petercai/Vision/blob/master/uml/umls-FeedRefreshTaskGiver.yaml" target="_blank">instruction example</a></em></sub>

  </div>
- Use `--config` with `umlc-gen` and `umls-gen` for repeatable generation.
- Keep generation rules in repository-scoped YAML files for team consistency.
- Store outputs under versioned folders such as `uml/plantuml/` when reviewing changes in pull requests.

## Ecosystem: UMLMark Suite

Together, these tools support a full code-to-architecture workflow:

| Tool | Role |
| --- | --- |
| [UML Gen (CLI)](https://github.com/petercai/uml-gen-java) | Generate class and sequence diagrams from source code |
| [UMLMark (VS Code Extension)](https://github.com/petercai/vscode-umlmark) | Interactive PlantUML preview, code navigation, export |
| [UMLMark (Eclipse Plugin)](https://github.com/petercai/UMLMark-release) | UML generation and usage inside Eclipse |

## License

This project follows a dual-license model across the UMLMark Suite.

- Free for Non-Commercial Use: [LICENSE.txt](LICENSE.txt)
- Commercial Use Requires License: [COMMERCIAL_LICENSE.txt](COMMERCIAL_LICENSE.txt)

If you need commercial usage guidance for your deployment scenario, contact the maintainer.

## Support

If UML Gen helps your team, support the project here:

- Support me: <https://paypal.me/petercaica>

## For Contributors

Run local checks and packaging commands before opening pull requests:

```bash
uv pip install -e .
python -m build
```

Track issues and feature requests in the GitHub issue tracker: <https://github.com/petercai/uml-gen-java/issues>.
