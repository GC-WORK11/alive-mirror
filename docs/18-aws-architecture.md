# docs/18 — AWS architecture (deploy plan)

Rules require AWS in the running system *and visible in the video*.
This is the smallest set that is real, not sticker-slapping.

## Architecture

```
Mobile app (Android/iOS)
   |  HTTPS
   v
App Runner service "alive108"   <-- server/Dockerfile, server/deploy-aws.sh
   |  FastAPI decision engine
   +--> S3 bucket "alive108-data"
   |      data/climatology.parquet   (9M-measurement decade product)
   |      data/community/obs.jsonl   (donated traversals — durable form
   |                                  of today's data/community.json)
   +--> DynamoDB table "alive108-community"  (optional step-up:
   |      obs + reports keyed by ts — scales past JSON file limits)
   +--> Open-Meteo / OSRM / Photon / FIRMS (external, free)
```

## Migration path from today's code (each is one focused change)

1. **Deploy** — `server/Dockerfile` + `deploy-aws.sh` already build and
   push the image and create/update the App Runner service. One command
   once AWS creds exist.
2. **Climatology on S3** — `history_builder.py` already produces the
   parquet; add `aws s3 cp` + read via `smart_open` or download-on-boot.
   The data is already AWS-shaped (OpenAQ itself serves S3).
3. **Community ledger on DynamoDB** — `community.py` keeps its exact
   function signatures; swap `_load/_save` file I/O for boto3 table
   ops. ~40 lines. Until then the JSON file is honest and works.
4. **Video proof** — screen-record the AWS console (App Runner service
   running + bucket) for ~10s, plus the public URL serving `/health`
   and the app pointing at it (EXPO_PUBLIC_API_URL).

## Free-tier cost

App Runner 1vCPU/2GB ≈ $0.007/min while running (~$5 for a demo window,
well inside the $200 credits the event issues). ECR storage + S3 +
DynamoDB stay within always-free limits at demo scale.
