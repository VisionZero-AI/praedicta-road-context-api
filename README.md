# Praedicta Road Context API

**Predictive Infrastructure Intelligence from Praedicta Inc.**

The Praedicta Road Context API provides machine-readable structural road context for infrastructure, mobility, and AI applications.

Production API: https://api.praedicta.ai
Interactive documentation: https://api.praedicta.ai/docs
Praedicta: https://praedicta.ai

## Current Coverage

The current research-preview deployment covers Pittsburgh, Pennsylvania.

- 19,628 road segments loaded
- coordinate-to-road context lookup
- canonical segment lookup
- multi-point route-context summarization
- retrospective spatial out-of-fold validation
- explicit distinction between validated and out-of-cohort road segments

Current model version: `0.2-research-preview`

## What the API Provides

The API exposes structural characteristics associated with road segments, including:

- road class
- segment length
- speed limit
- number of lanes
- road width
- network-node complexity

For road segments inside the retrospective validation cohort, the API can also return a structural percentile derived from spatial out-of-fold validation.

A percentile is a relative structural-context measure within the validated cohort. It is not a calibrated probability that a crash will occur.

## Endpoints

### Service Information

`GET /`

Returns service metadata, coverage, available interfaces, methodology, and major limitations.

### Health

`GET /health`

Returns service status, loaded road-segment count, and model version.

Example: `curl https://api.praedicta.ai/health`

### Coordinate Context

`GET /v1/road-context?lat={lat}&lon={lon}`

Matches a submitted coordinate to the nearest actual Pittsburgh road segment within the API matching distance.

Example: `curl "https://api.praedicta.ai/v1/road-context?lat=40.4406&lon=-79.9959"`

The API first resolves the actual nearest road segment. It does not substitute another road merely because that road belongs to the validation cohort.

If the matched road is outside the validation cohort, its structural percentile and tier are returned as `null`.

### Segment Context

`GET /v1/segments/{segment_id}`

Example: `curl https://api.praedicta.ai/v1/segments/13970`

### Route Context

`POST /v1/route-context`

Accepts an ordered collection of geographic points and summarizes the unique road segments matched from those points.

The route-context endpoint is a contextual summarization interface. It does not calculate or optimize routes.

## Validation

The Pittsburgh model uses **retrospective spatial out-of-fold validation**.

The research question was whether structural characteristics of the road network contained information associated with where road segments with no observed crashes during 2022-2023 subsequently experienced crashes in 2024.

The zero-history validation cohort contained 16,484 usable road segments after geometry filtering.

Observed spatial out-of-fold performance:

- ROC AUC: 0.7846
- Average Precision: 0.1696
- Average Precision lift over the base positive rate: approximately 3.56x
- Top 5% structural group: 824 segments
- Subsequent positive segments captured in that group: 188
- Top-5% capture rate: approximately 23.9%
- Top-5% precision: approximately 22.8%
- Top-5% lift: approximately 4.79x

These results describe retrospective validation performance. They do not establish prospective crash probabilities or causal relationships.

## Validation Scope

Not every Pittsburgh road segment belongs to the retrospective validation cohort.

The API separates the full Pittsburgh road network used for nearest-road resolution from road segments eligible for the retrospective validation analysis.

For segments outside the validation cohort, `percentile` and `tier` are returned as `null`, and `in_validation_cohort` is `false`.

A `null` percentile means that a validation percentile is unavailable. It does not mean zero risk.

## Intended Uses

The API is designed as a research-preview context layer for experimentation involving:

- infrastructure analysis
- mobility systems
- geospatial applications
- transportation research
- AI agents and decision-support systems
- physical-AI context enrichment

Applications should preserve the API validation scope and limitations when interpreting outputs.

## Important Limitations

The API does **not** provide:

- calibrated crash probabilities
- safety certification
- safe/unsafe road classifications
- route calculation or route optimization
- causal estimates of crash risk

Traffic exposure is not currently controlled through an ADT or equivalent traffic-volume variable.

Structural percentile should therefore be interpreted as a research-derived relative structural-context measure, not as an absolute measure of road safety.

## Developer Documentation

Interactive API documentation: https://api.praedicta.ai/docs

OpenAPI schema: https://api.praedicta.ai/openapi.json

The OpenAPI interface allows developers and machine clients to inspect the API contract programmatically.

## About Praedicta

Praedicta Inc. develops GeoAI and predictive mapping systems for infrastructure resilience and decision intelligence.

https://praedicta.ai

---

**Research preview - v0.2**

Praedicta Road Context API outputs should be interpreted together with their validation scope, data-quality indicators, and stated limitations.
