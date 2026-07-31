# ADR-009: ChartSpec Specification & Rendering Responsibility

* **Decision ID**: `ADR-009`
* **Status**: `Proposed`
* **Context**: Financial analysis reports require visual representations (Bar, Line, Stacked Bar, Pie charts). The system must decide how charts are specified, generated, and rendered across client platforms.
* **Decision**: Enforce **Backend JSON `ChartSpec` Generation with Client-Side Native Dynamic Rendering**:
  * LLM / Backend Orchestrator DOES NOT draw pixels or generate binary chart images.
  * Backend emits a versioned, type-safe `ChartSpec` JSON contract bound to a `result_dataset_id`.
  * Flutter Mobile Client renders native interactive vector chart widgets using `fl_chart` / `syncfusion_flutter_charts`.
* **Rationale**: Native client rendering provides fluid interactions, theme support (light/dark mode), tap-to-drill-down capabilities, crisp scaling, and reduced network payload sizes compared to downloading static server-rendered PNG images.
* **Alternatives Considered**:
  1. *Server-Side PNG Chart Rendering (Matplotlib/Seaborn)*: High latency, bandwidth consumption, and static non-interactive image limitations (PNG export remains available as a secondary utility).
  2. *LLM Generating HTML/JS Code (Chart.js)*: Security sandbox risks and inconsistent rendering in Flutter WebViews.
* **Security Impact**: Eliminates code execution risks associated with rendering dynamic web scripts inside mobile WebViews.
* **Data Integrity Impact**: `ChartSpec` data points derive directly from validated `financial_facts` records bound to `result_dataset_id`.
* **MVP Impact**: Delivers a responsive mobile user experience.
* **Cost Impact**: Reduces backend CPU and storage usage by eliminating server-side image rendering pipelines.
* **Scalability Impact**: Offloads graphics rendering compute entirely to client mobile GPU/CPU.
* **Risks**: Ensuring chart package cross-platform visual consistency across iOS and Android screen densities.
* **Revisit Trigger**: Requirements emerge for automated PDF export generation requiring server-side headless canvas rendering.
