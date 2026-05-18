# Câu trả lời nộp bài Lab 28

## 1. Phân tích trade-off kiến trúc

Nền tảng này cân bằng giữa performance, reliability và maintainability bằng cách tách hệ thống thành hai phần: hạ tầng local chạy bằng Docker Compose và tầng serving mô phỏng Kaggle qua `mock-kaggle`. Kafka giúp tách ingestion khỏi processing, nên producer và consumer có thể retry độc lập. Prefect điều phối luồng dữ liệu từ Kafka sang lớp Delta-style parquet, Redis đóng vai trò online feature store nhẹ, còn Qdrant cung cấp vector retrieval cho API gateway. `mock-kaggle` giữ latency ổn định khi demo và tránh rủi ro từ tunnel bên ngoài, nhưng vẫn giữ cùng interface HTTP như vLLM và embedding service thật.

Về reliability, stack dùng ranh giới service rõ ràng trong Docker Compose, health endpoint, seed script có thể chạy lại, và Prefect metadata lưu bằng Postgres thay vì SQLite để giảm lỗi lock database. Về maintainability, mỗi integration point nằm trong một script hoặc service nhỏ với input/output rõ ràng, nên khi lỗi xảy ra có thể cô lập nhanh bằng Docker logs và smoke tests.

## 2. Xử lý mất kết nối giữa local và Kaggle

Submission này dùng `mock-kaggle` làm fallback cho Kaggle GPU serving. Nếu Kaggle thật hoặc tunnel ngrok/cloudflared không khả dụng, mock service local vẫn cung cấp `/v1/chat/completions` và `/embed`, vì vậy API gateway, bước seed Qdrant, smoke tests và demo dashboard vẫn chạy được. API gateway cũng xử lý trường hợp Qdrant chưa có collection `documents` bằng cách tiếp tục trả lời với retrieval context rỗng thay vì crash.

Khi chạy chế độ Kaggle thật, có thể trỏ các biến môi trường `VLLM_NGROK_URL` và `EMBED_NGROK_URL` sang URL ngrok hoặc cloudflared. Khi chạy fallback mode, các biến này trỏ về mock service local.

## 3. Kafka giúp decouple các component như thế nào

Kafka tách data ingestion khỏi các bước xử lý phía sau. Producer chỉ cần ghi event vào topic `data.raw`; producer không cần biết Prefect chạy lúc nào, parquet được lưu ở đâu, hay Redis và Qdrant được populate như thế nào. Prefect có thể consume topic sau đó, retry khi xử lý lỗi, và replay dữ liệu mà không cần thay đổi ingestion script.

Thiết kế này giúp platform dễ mở rộng hơn vì có thể thêm consumer mới mà không sửa producer. Nó cũng tăng resilience vì khi một service downstream tạm thời lỗi, dữ liệu đầu vào không nhất thiết bị mất ngay.

## 4. Observability được implement ra sao

API gateway expose Prometheus metrics tại `/metrics` thông qua `prometheus-fastapi-instrumentator`. Prometheus scrape API gateway, còn Grafana dùng để quan sát tình trạng service và request behavior. Docker Compose logs hỗ trợ troubleshooting ở mức service cho Kafka, Prefect, Qdrant, Redis, Grafana, Prometheus, mock Kaggle và API gateway.

Production readiness được kiểm tra bằng `scripts/production_readiness_check.py`. Script này validate health endpoints, metrics exposure, Qdrant, Redis, Kafka topic state và basic security behavior. README cũng có các lệnh log tập trung để phân loại lỗi thành blocking, ảnh hưởng test, hoặc noise không nguy hiểm.

## 5. Khi một service crash thì hệ thống xử lý thế nào

Nếu Qdrant crash hoặc collection `documents` chưa tồn tại, API gateway vẫn tiếp tục trả lời với retrieval context rỗng. Có thể khôi phục bằng cách restart Qdrant rồi chạy lại `scripts/05_embed_to_qdrant.py`. Nếu Kafka crash, Docker có thể restart service và ingestion có thể chạy lại vì các sample script đủ idempotent cho demo lab.

Prefect dùng metadata lưu trên Postgres để giảm lỗi database lock và giúp orchestration state ổn định hơn. Redis và Qdrant có thể được seed lại từ manual run sequence. Quy trình recovery chuẩn là chạy `docker compose ps`, xem log tập trung bằng `docker compose logs`, restart service lỗi, chạy lại seed script tương ứng, rồi chạy lại smoke tests.
