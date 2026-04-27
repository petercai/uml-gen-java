# uml-gen

<p align="center">
  <b>Generate UML diagrams directly from source code — fast, simple, developer-friendly.</b>
</p>

<p align="center">
  Turn your code into <b>architecture diagrams</b> in seconds.
</p>

---

<p align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen">
  <img src="https://img.shields.io/badge/python-3.12+-blue">
  <img src="https://img.shields.io/badge/license-dual--license-orange">
  <img src="https://img.shields.io/github/stars/petercai/uml-gen-java?style=social">
</p>

---

## ✨ Why uml-gen?

Navigating and understanding large Java codebases is hard.

**uml-gen** helps you:

* 🧠 Visualize architecture instantly
* 🔍 Understand class relationships
* 🔄 Trace method interactions (sequence diagrams)
* ⚡ Integrate into your dev workflow (CLI / CI / IDE)

---

## 🚀 Features

* ✅ Generate **UML Class Diagrams**
* ✅ Generate **Sequence Diagrams**
* ✅ Output **PlantUML** format
* ✅ CLI-first (scriptable & automatable)
* ✅ Works with VSCode / Intellij ecosystem
* ✅ Fast, minimal dependencies

---

## 📦 Installation

```bash
pip install uml-gen
# or
pipx install uml-gen
```

Or from source:

```bash
git clone https://github.com/petercai/uml-gen-java.git
cd uml-gen-java
uv pip install -e .
```

---

## 🧪 Quick Start

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

---

## 📊 Example
- PlantUML Class Diagram
  ![umlc-CategoryController](https://www.plantuml.com/plantuml/svg/lLfTRXit47xVKn3eGri4yiQMP5j-2E8eJb2WQL8xzajW5DGkBR7PFv2K4lNd57th3NgD7gKdwN3_nDqbgLtjsa22GCkPxnlE36Uuitd91MPY7GO8_dgZEHPa6RFjF8u4YuE0i5zUaqIiniwtw2s928Dr7ossKdgq9152__w3Ff0a8IoaaG2fbH09lt3T9HMhzUB8YqCt8O8m3rCtLnhzYZTuZ-WTvJIENC48SKFCuQdKRgK4Gl3dVI9eI7y3QnzYXZQKVA7H4dq1BNHtW-QnJz0pTFlkntUOVUwqYGttG7a4reIWcf5TUG5DE44u0A482xeX5mU1vpeZHWA2EL6a9HaHIO0zSaGokgEOBLqF8aKYuHRs10Gyx2CH9yY3vuGv27tw1Akk8S17Mnm65yVelx__sYTrV-z8x8p2aHGYHejOY3X4FcN44zBzAmg-9M4YjYWauO8mxZXUW3b7MNm0z84krv1Ay0Diuyo3tT78bMdXIY-axd0tMGg0VqBuHwDx91KkJexlxz7liCjd_R76npeRl_iUDZu8_dIAbaJSWKk6XPr9sBTKp46GYXJupzpdbmik6FR46xoXa2jlYF1MXEtdVCZaNRr-ndiyRk_wDdWd9-X1_iuzyyr0g1D4-HqEgFy3B5qJdiGH9nKdlI74_tbDreIte0HPTwUGStJnX0vWF4C2VoRjSqABCZr1sFTxWXmVGvP21Nk5lSzzeU10KNuP1A_ZgEdnQ_B025_98aE-YWuKLSMSwla14T02dMcCgzX-irvmZz547i3Nb-_tyoNom4CFYppY-ZXsQm0vxtdx3RG2dAJ5vZPY1FlpU1tfwy8xQ6P1DqPeArHitGh2RWzAW0-2bOevskGmZpI1e0I8-4Omk08qih3eTGTp500vrsblewk0ax7PzYjepuSRdchlccWTTvxTBFh1vo2xWDPPRWGMwnPbrqQIOUGxwL07sc92VwqzRryNstASZhKSZMX_nCj-f03GlNkt0eHYhpuSnaSxz4aJNVMEMWCFfbH1YdRGsqjDqF69_apVyZPNCmsDL1p4tXtGz1pnLRmEYaueTy8lYoP2vQl50xoCfBxtief52RycISofw5nFMQddcW3xdU_s1709fP7_QliJ3ZlSnmxZEfKj-jLMUbthM8ZAW5vje7L_Wpe0VPpwy-ehgEtolRdDBK-htg2RrM0MZXzioqQEyVDTS2-ZIXM0dsaT6oIzx4PateUEmXZfy6PmC5-QqTULA-UZ4awUws-vrGGRAgaUw-mqSITv5Rh6NsvPC8WVTUKd8oaO6cvJSdOm5-en1wtkTewYm4l93uILnVTnMKjVFmtTBALBQqymKFhO-E16K-raZyisKKAeloVV4BQXaCQTRE2Pabj7oQzMqyEIquuAYI47jptwWHr_Ca5onlze-ATdgVrvXxdABW7DstdVS5GZCUiVYMeGPggL_TrKZK3MWz-pEJGfCJJwz2mRckQZJ-jxKVyeDC7wzS5MuECPoil1OWZlcMWWJaz2S_OaD6TJj8wUWkZy5B7i5V7WJjEAPpQnpJERdwpscm0s2nSdrDLyxyelb-spUY_O-RcqNzqUr-wW9PKlOhSwAPoLqxLkiv0IJZFzw72iRJ1Jj5ZJeDggbKXs05UqTeD_np5yvXgDNgH5q56-y1JFb5k5Rhdw0K0duMW-OhHPItkeK_-A85ULpQK0yF2F5zLHlLEPMUzVVv4EbPfFwqVDsSsJ3Q35ehB1wYDru6jQpaQRfjMFUEdKaQpcx6HKrzQ7opQ4KiJcafgGYSMq4qMW34OvpBKPbwthjUgcLCwy0RGcem0tLieOQrUAL39BgD5Enve6axIZmrIsmTCSXfLoEpVeX9JTc2PDLIGbIyqAXeJPfr0rrIHPhmHQMntREtefrR3Gh54_siLziIoPUaspGYCQTb6DDymAzKWrZAs1gElwTg65QQHu5yDjUZPdslJottlbicwrLsolWF6iguBrVBLkG4r8pRsjaDEL1fkyAH0M5LCCB2fgBjhaD1umYTUk0YOnpV__COcMCRCOs4QcJQZKq5Uk61LbRPEmIwZ0Bqdao_y0-3y=)
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
  ![umls-FeedRefreshTaskGiver](https://www.plantuml.com/plantuml/svg/xLpTZjku5RwVfn1oqnR5nDQ_v8jYaybCii2ccsOokmMo0uEMEHusicH8j3Ephz6xla5Veu_I9-cHHCcII4hMpw3s940MEpeKVxxla8Vda4V-8QOeejkrhy1_yVaLnikF-2x2yVqd57zvItOuElk3yXO7E48KBvN5O_BY-Ge7YlAVVoiVy6Q3epK9ABnrJ-acdaqcAqBljukNNhYUR335aOV8X5Kw_mVQePPNVo4n2OC9ZJ2Uh54CqgJsGPNW9VZtyuQIDVaTHdiNHigEuAyaM2bVePRooxLo4IwnycVbvlrFxr7qfHE8NUn1vNCOpHggPfrTUZxPn5X1FhmK80gCpNerpkgSHzZ7ACQbjvFECDtuoCClSTRTop1QJRmme3YWatmyFWQ6bmeDDue7Sj2Sedp-3AKJgMvVFgArFrEL__xhd-tltTwU9UrdtPpT4-3nBWpf8dmuYx-GO8CYj5O-m7GY7jcWW7v0osN2l3OjbRyE7tAvEWMGQ4j3v05jCBqKqE0PF83MNhnA_lT2GR6I_ZMVdctsBIilH8ES_HQ8n6aZeeAv2lJ4aGS4as2IpCn9eeXK8vDTDWlleDv4o4Zo_im5JhXn_MsBjpXceyaUYZ5aZtEjGyzPbQm_JQzt-6e9S-lLXa1t-PyPQ-nXhfUxMkKBcUyFRKWwewBGzq6Qry_wrMqHKCR9ho7CpnhxcQnEVIQT6zrvpseo4apHOAumzUwBOR2dOW3iUMvsw9hLaJ7_3fRdMqnfskV-8Uro_pYt3knnNoNhq11I3iihBa1c3mN6x75kTu2OLM4wraGTtb3YvtCv_RleBdsQEnrwIsimTCALmvHziraYMfzHJ5YVKamyTxlFALQLeHTEgkoLQnpjY8Tp5igoFHjbwLoTjWy7jeMOmFOMU7WIP_KcN4jiyWbL0pO-8ZZ-Y3TXJC16Fh81Sl9Ya5p9N3t01fO76XLL9y86sNXLqNWluUN7YspJgb8gA2d6B2YRgmVOJnczWlQoGQl2GIS87zbEAwPQK5eXN50-L_N1j0kQPJY4XYE5VKKIBmNsNW7zzRAg0kgbS_K08zweWdgBCYFqORkuXd_5W2lFwI0hahbwW8dF1rEfoGR0sVcInRXym1xuApNBb4lhfYcNpzL3zm11PQRJn3gTCKz8EV-Bp9-PAPiez70S__5FlmKUWfqSpuRwEFfKs5jUU7lBUefcdzDvgP30yxVW9uVH4aUtPvAXCX25GpHJAFg2Uusxx27fhiABocCSoeRHn8Pnc-4jKF4e8tn7V7ymJilYS5fMBvpb9WoTQzNGsp61GpyOaAbnNPlQO42smRLg7w2aumLaEdohZW1GoV-VAJ7QILPMtu100wl0IGQ3KwSyEf3TjXcHUdWnKxQf4vMK3R64vQZ3iFckzfxwUFR5Qh8lLfMA0d0B3sDnmAQqi6G81nKsNIdFRZFwVOmtK-wIltl1haHzkgO8P6D1PMjPMCAWxZ41o4fKELDMcBuc0OeUE-EinvgsfV2YNYYhJBa2zX8bLe0y9J3Nu82vHcTW73SsJvSjKbWbAWVVBFcprwGin-c6fl2YuSfYMtzDnb0L81YeFFO7NO6XZYy3BqoEz7fXAvqAg5DBuKMzi5NeSNZ6yWMM8-60uGSQ8O--mPwFeYHc6GUYfXfrY23g1R72aiqJPxT1N4Ap7XrDUPhAZI4v21Y83E8vNjGwBMb4rZy6E-IJvT_N_iKzIdG9uUXGa3gBXggYuJFKvMUesmeomkcbm3kwzY6a9fJW-5T2x_-wNKDWxUMYmNhL-KMf3r-Kfiv1DcNcfcH3xr6mzF5L666o2f8Ba-rci4NDPsvDDXoYnKEq912FDlYeaA8BYDBLTgt1Zlw9K7_uvgVQ_Eu7ik6guhU8mWSxPLogpIypaBKZkoF1yjrsCHoOO_83SCpX2kCjfYcpc3LOrzY_6uxB5U1oX-EofboprlI0xMuBtVOCz4g6tU9sDsluvcRpPj2McS6IgjBD6p2zwOkheXeMljTamx7npHQXGBFTI0_1ixkUSH3gFCrZxDDT49xAXEIDlIqpzYL8uQj57FfRYc-YVkUtvVjFWmi3GFIaoAHX08a_OZ_DN1cCokB2410D3G4Cavi483feaR5xlk6Bon9ipzRmxTdXrwmZCuqdihWStbuuXrd4u_Qa7DxXSDf3jADMbSlxXgxCDJo9-CJbpPzxW1T_4fw6EXN4NbDPx5KweCFqEemeNduYQnnJjDuCFX4mD9qpo4b-r624WbXbsdu4YNOuGYkSu7kDwLUCWyiiBMKmJdOTLHMDW9Ct9I1hswQFMv7b9bI-LLMNdO-NRstOcMjQkQUFLJc_PjjhJJR2MRcWNSCwzHi0Ht1TKsnn9tqHnHp8ckpKzMKABYUJJLICweXzaWe2Mp0BxPQRtpssnPRuopSaHWiVn0781v_uMzor1eZ6kWAsfBVTLWjc_gu_EnhFSjh6kl5NLKisG2WQYmL7oe9p60lxBE2nKZygoS6MBUWiBngB15ULaU2gLHBsQEKiW9EUdZ2Dna5-II8f6y92fIr7pdKHHyfuu9Am-_7G8JCxFyOHbOn6YMgOSkgD_3AK0yz84IPzPoVXbmy0i-FLRuziS5qyZhoq2qyTL6EgCjMOQWjbafppZBIVeui8Tzm-EoUZQrFPGFBofsBDbhAMhpu9EwNf9abvVx999y-5Tvl6bByp1fLoJHajcZGEelNutBVEJB3BuuRoZana3i-GCzvo5WwVsT4nfVNf294dASKUsk0VhoAqnXSzi_xBW7bVL-lfwvQRC7XcZUc1qDQhCN0vN0gBrlCSe0A2RxKu1NZ-grbhcRpQjxQQlnDI0wot4AAt4dBiNp5qvyHiuQJ9cpzLDWJE9BjF5POSufoBlaTCtCj4-XubHqVnQ65Vm-UAjYuVKlx6Kp7eI1bqokjAnDJH7dJsK07RsXlV-ARuS5hvSBuD6sERiXLYczqFrCOwNQsUtjWDXshsU8Tg-OTrah86DhYFgs5MR1Un5v55f_MHwqhmoRMXAaBfUEYT1fQT9CZYK0foxTVX3d-A4F6JzUIZkD_dPPMhLZvRIkjqdDn0ggcBI4qpx6LWZot5emcTAqJdFWzq4Ci9fSy4dN2vMqtBy9JGQK9qsZD19xGgrZEnAfOXH6Sy4tIc49qfGLVByGZmrmkVz3c8g2Tqg8x69Nc0R2IKjj1ssassK_1pBKagKl8qwClvwa-uMAQeixqIna4ldC75Bru8a9ue1otzM0tzM8SjvnNPuTV8-p9uJUTViDPa8sdS4LfaH_QZBNk7DWYZDVB9x_Zcuq-3Fn6rk4H9rUgNA5bbYV-HcpJhv7H_laLb5xirMKiuUgJJiZdeKXkI5eelkB_FpnESdyyd_SwL_gYFQpTZFf4bMKdOO_drugBl2_BxWlp_BqXLdKhdgDg2-XINf2hzHIqe0hW_u62P_Fhv_m0=)

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

---

## 🔗 Ecosystem (UMLMark Suite)

This project is part of a growing ecosystem:

| Tool                            | Description                            |
| ------------------------------- | -------------------------------------- |
| **UML Gen (CLI)**               | Code → UML generator (this repo) [(examples)](https://github.com/petercai/Vision)      |
| **UMLMark (VSCode Extension)** |[ Visualize & navigate UML/code interactively](https://github.com/petercai/vscode-umlmark) |
| **UMLMark (Eclipse Plugin)**    | [Generate UML directly inside Eclipse](https://github.com/petercai/UMLMark-release)   |

👉 Together, they provide a full **code ↔ architecture workflow**

---
## 🛠️ Roadmap

* [ ] Advanced sequence analysis
* [ ] Large project optimization
* [ ] CI/CD integration
* [ ] Team collaboration features

---
## ⭐ Support the Project

If this project helps you:

* ⭐ Star the repo
* 🔁 Share it
* 💼 [Buy Me a Coffee](https://paypal.me/petercaica)

---

# ⚖️ License (Dual License Model)

This project uses a **dual-license model**.

- 🟢 Free for Non-Commercial Use

  You can use this project **for free** if:

  * Personal projects
  * Learning / education
  * Open-source development

  See: `LICENSE.txt`

- 🔴 Commercial Use Requires License
  A **paid license is required** if you:

  * Use in a company or organization
  * Use in production systems
  * Provide it as part of a SaaS
  * Integrate into a paid product

  See: `COMMERCIAL_LICENSE.txt`


---

<p align="center">
  <b>© 2025 Peppermint</b>
</p>
