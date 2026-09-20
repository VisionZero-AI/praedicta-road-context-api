# Praedicta Road Context API

Research-preview API for machine-readable structural road context.

## Endpoints

- GET /
- GET /health
- GET /v1/road-context
- GET /v1/segments/{segment_id}
- POST /v1/route-context

## Production start

uvicorn api.main:app --host 0.0.0.0 --port $PORT

## Important

This API provides structural-context research outputs.

It does not provide:
- calibrated crash probabilities
- safety certification
- safe/unsafe road classifications
- route planning

Current Pittsburgh model:
Retrospective spatial out-of-fold validation.
