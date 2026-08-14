# Finance Intelligence — Devir Notu (2026-08-14)

Bu belge, staging ortamının kurulduğu ve uçtan uca doğrulandığı çalışmanın devir notudur.
Repo kökü: `/Users/korhanturgut/.gemini/antigravity-ide/scratch/finance-intelligence`

## Proje ve mevcut durum

Finance Intelligence: Flutter iOS uygulaması (`apps/mobile`) + FastAPI backend (`services/api`) +
asenkron worker (`services/worker`) + Postgres. Belge yükleme → ayrıştırma → veri doğrulama →
AI analiz hattı var. Aşağıdakilerin TAMAMI canlıda uçtan uca doğrulandı:

1. Firebase e-posta/şifre girişi → `POST /api/v1/organizations/bootstrap` → org oluşturma
2. Belge yükleme → GCS → worker ayrıştırması → `ingestion_status: COMPLETED`
3. AI analizi → `POST /api/v1/analyses` → worker → gerçek Claude çağrısı → `COMPLETED`

## Altyapı topolojisi

| Bileşen | Nerede | Detay |
|---|---|---|
| API | Cloud Run `finance-api`, us-central1, proje `finance-intel-staging-8f2a` | `https://finance-api-523958262212.us-central1.run.app`, ENVIRONMENT=staging, rev 00006 |
| Veritabanı | PostgreSQL 14, `tm-backend` VM (proje `travel-mapper-9dffe`, e2-micro, us-central1-a) | `34.173.174.163:5432`, db `finance_intelligence_staging`, SSL+scram zorunlu. DİKKAT: Bu VM aynı zamanda TravelMapper prod backend'ini barındırır — dikkatli ol. |
| Worker | Aynı VM'de systemd servisi `finance-worker` | Kod: `/opt/finance-worker`, env: `/etc/finance-worker.env` (root, 600), Python 3.12 venv, MemoryMax=400M |
| Depolama | GCS bucket `fi-staging-documents-8f2a` | Yüklemeler `{org_id}/{key}`; API SA objectAdmin, VM SA objectViewer |
| Kimlik | Firebase (aynı GCP projesi) | iOS app `1:523958262212:ios:bd7b9a3d73ee327cba6c91`, e-posta/şifre etkin. Backend `FirebaseIdentityVerifier` ile doğrular. |
| Alan adı | `finapi.korhanturgut.com` → Cloud Run domain mapping | DNS doğru (CNAME ghs.googlehosted.com) ama sertifika Google'ın TLD kotasına takıldı, otomatik yeniden deniyor. Mobil şimdilik run.app URL'sini kullanıyor. |

## Gizli değerler (Secret Manager, proje finance-intel-staging-8f2a)

Değerler ASLA koda/loga yazılmaz; isimler:
`fi-api-db-url`, `fi-worker-db-url`, `fi-bootstrap-db-url`, `fi-maintenance-db-url`,
`fi-owner-db-url` (migration, psycopg2+sslmode formatında), `fi-pseudo-salt`,
`fi-ingestion-hmac`, `fi-anthropic-key`.
DB rolleri: db_owner (migration), db_api_user, db_ingestion_worker, db_bootstrap,
db_maintenance_worker (+ legacy `db_app_user` NOLOGIN). Staging validator dev şifrelerini
ve localhost'u reddeder (`app/core/config.py`).

## Anthropic entegrasyonu

- `ANTHROPIC_BALANCED_MODEL_ID=claude-opus-5`, `ANTHROPIC_FAST_MODEL_ID=claude-haiku-4-5`,
  `ANTHROPIC_TIMEOUT_SECONDS=300`, `ANTHROPIC_MAX_OUTPUT_TOKENS=16000` (Cloud Run env + worker env).
- `orchestration/engine.py`: `use_fake_transport` artık `not settings.ANTHROPIC_API_KEY`
  (eskiden True sabitti — bu bug düzeltildi).
- Kalite kapısı çalışıyor: anlatıdaki sayılar doğrulanmış veri setinde yoksa iş
  `UNSUPPORTED_NUMERIC_CLAIM` ile FAILED olur (fail-closed, bilinçli tasarım).

## Bu çalışmada eklenen/değişen dosyalar

Backend:
- `Dockerfile`, `.gcloudignore` (yeni; `storage/` kalıbı köke `/storage/` olarak sabitlendi)
- `services/api/app/storage/gcs_adapter.py` (yeni GCS adaptörü), `storage/factory.py` (yeni),
  `core/config.py`'ye `STORAGE_BACKEND`/`STORAGE_BUCKET`; `documents.py` + `ingestion_worker.py`
  fabrikaya bağlandı. LocalStorageAdapter yalnız development.
- `api/v1/organizations.py`: `POST /organizations/bootstrap` (token-only onboarding, idempotent)
- Migration `032_bootstrap_self_onboarding` (SECURITY DEFINER `bootstrap_self_organization()`,
  EXECUTE → db_bootstrap) ve `033_worker_queue_visibility` (SECURITY DEFINER
  `fetch_next_queued_ingestion_job()` — worker RLS yüzünden kuyruğu göremiyordu).
  Alembic head: `033_worker_queue_visibility`.
- `services/worker/app/main.py`: kuyruk yoklaması 033'teki fonksiyona geçirildi.

Mobil (`apps/mobile`):
- `lib/firebase_options.dart` (yeni), `lib/core/security/firebase_security_adapters.dart` (yeni:
  FirebaseIdentityTokenProvider + NoopAttestationTokenProvider)
- `lib/app/app.dart`: release'te AuthGate (authStateChanges → SignInScreen | shell) +
  OrganizationGate (bootstrap çağrısı, OrgContext doldurur)
- `lib/features/authentication/views/sign_in_screen.dart`: gerçek e-posta/şifre giriş+kayıt UI
- `lib/core/network/org_context.dart` + `interceptors/organization_interceptor.dart` (yeni:
  `X-Organization-ID` başlığı — daha önce hiç gönderilmiyordu)
- `lib/presentation/providers/providers.dart`: config artık kReleaseMode ile seçiliyor
  (eskiden hep development'tı) ve prod'da Firebase sağlayıcıları kullanılıyor
- `lib/core/config/app_config.dart`: prod URL geçici olarak run.app (`/api/v1` yolu düzeltildi;
  finapi sertifikası gelince TODO'daki gibi geri çevrilecek)
- `pubspec`: firebase_core + firebase_auth eklendi

NOT: Bu değişiklikler commit EDİLMEDİ — ilk iş olarak anlamlı commit'lere bölüp commit et.

## Runbook

API deploy (repo kökünden, cwd önemli — ev dizininden çalıştırma):
```
gcloud run deploy finance-api --project=finance-intel-staging-8f2a --region=us-central1 --source=. --quiet
```

Worker deploy:
```
tar --exclude='__pycache__' --exclude='.venv' -czf /tmp/wc.tar.gz services packages requirements.lock
gcloud compute scp /tmp/wc.tar.gz tm-backend:/tmp/ --project=travel-mapper-9dffe --zone=us-central1-a
gcloud compute ssh tm-backend --project=travel-mapper-9dffe --zone=us-central1-a \
  --command="sudo tar -xzf /tmp/wc.tar.gz -C /opt/finance-worker && sudo systemctl restart finance-worker"
```

Migration:
```
DATABASE_URL=$(gcloud secrets versions access latest --secret=fi-owner-db-url --project=finance-intel-staging-8f2a) \
PYTHONPATH=$PWD/services/api .venv/bin/alembic -c services/api/alembic.ini upgrade head
```

Worker logları: `sudo journalctl -u finance-worker -f` (VM'de).
Sağlık: `curl https://finance-api-523958262212.us-central1.run.app/health`

## Test hesapları ve test verisi

- Firebase test kullanıcıları: `e2e-test-fi@`, `e2e-test-fi2@`(varsa), `e2e-analysis@korhanturgut.com`
- Org `e9b3034d-6fed-4d99-8543-edf6daa3a866`: parse edilmiş test-bilanco.pdf + `9999...` UUID'li
  seed kurumlar/dönem/adaylar/veriler (Garanti/Akbank Test). Org `cb51c1e6-...`: kurum+dönem seed.
- Bunlar silinebilir/temizlenebilir; prod verisi değildir.

## Bilinen eksikler / sıradaki işler (öncelik sırasıyla)

1. **Analiz istem-anlama katmanı taslak**: `orchestration/engine.py` içinde `NormalizedRequest`
   sabit kodlu (her istem "kurum karşılaştırma" planına gider, kurum/dönem/ölçüt seçimi
   isteme bakmaz). Gerçek normalizasyon (fast model ile istemi ayrıştırma) yazılmalı.
2. **Değişiklikleri commit et** (yukarıdaki liste).
3. **finapi sertifikası**: `gcloud beta run domain-mappings describe --domain=finapi.korhanturgut.com
   --region=us-central1 --project=finance-intel-staging-8f2a` ile izle; CertificateProvisioned=True
   olunca `app_config.dart` prod URL'sini `https://finapi.korhanturgut.com/api/v1` yap ve
   release build'i telefona yeniden kur.
4. **Firebase App Check**: istemcide entegre değil; sunucuda `ENFORCE_APP_CHECK=false`.
   Entegre edilince true yapılacak (mobilde NoopAttestationTokenProvider değiştirilecek).
5. Worker'ın sessiz hata döngüsü bir kez görüldü (`WORKER_LOOP_EXCEPTION_ENCOUNTERED`,
   detay loglanmıyor) — `services/worker/app/main.py:113` civarına `logger.exception` ekle.
6. Test verisi/hesap temizliği (istenirse).

## Sınırlar

- `tm-backend` VM'i TravelMapper prod'unu da çalıştırır: Postgres config'ine ve VM kaynaklarına
  dokunurken dikkat; finance-worker MemoryMax=400M sınırı bilinçli.
- Gizli değerler yalnız Secret Manager'dan okunur; koda, loga, dokümana yazılmaz.
- Staging'de dev-auth kapalıdır ve açılmamalıdır (`ENVIRONMENT=staging` kalmalı).
