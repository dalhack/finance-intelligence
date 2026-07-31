# ADR-001: Mobile Technology Selection (Flutter + Riverpod)

* **Decision ID**: `ADR-001`
* **Status**: `Proposed`
* **Context**: The Finance Intelligence mobile application requires rendering quarterly financial tables, dynamic charts (Bar, Line, Stacked Bar), real-time job progress indicators, and interactive evidence drill-down drawers on iOS and Android platforms.
* **Decision**: Adopt **Flutter 3.x** using **Dart 3.x**, **Riverpod 2.x** state management, **GoRouter**, **Dio**, **Freezed**, and **Firebase SDKs** (Auth, App Check, Crashlytics, Analytics).
* **Rationale**: Flutter provides vector chart rendering performance, a unified cross-platform codebase, strong type safety, and isolation of presentation logic using Riverpod.
* **Risk Reduction & Limitations**: Freezed DTO parsing enforces schema validation at the client network boundary. However, client-side validation alone does not prevent server API schema evolution errors or malformed payload transmissions from untrusted networks.
* **Alternatives Considered**:
  1. *React Native*: Lower vector rendering performance for high-density financial charts and JavaScript bridge serialization overhead.
  2. *Native Swift/Kotlin*: Dual engineering overhead maintaining separate codebases for MVP.
* **Security Impact**: No secret keys stored in binary; app integrity enforced via Firebase App Check attestation SDK.
* **Data Integrity Impact**: Type-safe Freezed model parsing handles JSON API responses.
* **MVP Impact**: Accelerates development by sharing UI components across iOS and Android.
* **Cost Impact**: Reduces mobile development cost compared to dual native teams.
* **Scalability Impact**: Client-side rendering offloads chart processing from backend servers.
* **Risks**: Third-party chart package licensing or rendering edge cases on extreme screen sizes.
* **Revisit Trigger**: Requirements emerge for platform-specific desktop extensions or native OS widget extensions.
