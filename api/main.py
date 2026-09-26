from pathlib import Path
from typing import Optional, List

import geopandas as gpd
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from shapely.geometry import Point


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_PATH = (
    BASE_DIR
    / "data"
    / "pittsburgh_full_road_context_api_v02.geojson"
)

MODEL_NAME = "Praedicta Pittsburgh Structural Road Context"
MODEL_VERSION = "0.2-research-preview"
MODEL_METHOD = "Retrospective spatial out-of-fold validation"

# Maximum distance from query point to a modeled road segment.
MAX_QUERY_DISTANCE_M = 50.0


# ---------------------------------------------------------
# Application
# ---------------------------------------------------------

app = FastAPI(
    title="Praedicta Road Context API",
    description=(
        "Machine-readable structural road context derived from "
        "Praedicta predictive mapping research."
    ),
    version=MODEL_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Load model output
# ---------------------------------------------------------

print(f"Loading road-context layer: {DATA_PATH}")

roads_wgs84 = gpd.read_file(DATA_PATH)

if roads_wgs84.crs is None:
    raise RuntimeError("Road-context dataset has no CRS.")

roads_wgs84["segment_id"] = (
    roads_wgs84["segment_id"].astype(int)
)

# Metric projection for nearest-segment calculations.
roads_metric = roads_wgs84.to_crs("EPSG:26917")

# Spatial index is built once at startup.
ROAD_SINDEX = roads_metric.sindex

# Fast ID lookup.
SEGMENT_INDEX = {
    int(segment_id): idx
    for idx, segment_id
    in roads_wgs84["segment_id"].items()
}

print(f"Loaded {len(roads_wgs84):,} modeled road segments.")


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clean_value(value):
    """Convert pandas/numpy missing values into JSON-safe None."""
    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def context_tier(percentile: float) -> str:
    if percentile >= 99:
        return "99-100th percentile"
    if percentile >= 95:
        return "95-99th percentile"
    if percentile >= 90:
        return "90-95th percentile"
    if percentile >= 80:
        return "80-90th percentile"
    return "Below 80th percentile"


def segment_response(row, distance_m: Optional[float] = None):
    in_cohort = bool(row["in_validation_cohort"])

    if in_cohort:
        percentile = float(row["predictive_percentile"])
        structural_context = {
            "percentile": round(percentile, 2),
            "tier": context_tier(percentile),
        }
        validation = {
            "scope": "zero_history_2022_2023_spatial_oof",
            "in_validation_cohort": True,
        }
        spatial_fold = clean_value(row["spatial_fold"])
    else:
        structural_context = {
            "percentile": None,
            "tier": None,
        }
        validation = {
            "scope": "outside_zero_history_validation_cohort",
            "in_validation_cohort": False,
        }
        spatial_fold = None

    response = {
        "segment_id": int(row["segment_id"]),
        "street": {
            "name": clean_value(row["streetname"]),
            "from": clean_value(row["fromstreet"]),
            "to": clean_value(row["tostreet"]),
            "road_class": clean_value(row["domi_class"]),
            "oneway": clean_value(row["oneway"]),
        },
        "structural_context": structural_context,
        "validation": validation,
        "factors": {
            "segment_length_m": clean_value(row["segment_length_m"]),
            "speed_limit": clean_value(row["speedlimit"]),
            "num_lanes": clean_value(row["num_lanes"]),
            "road_width": clean_value(row["roadwidth"]),
            "max_endpoint_degree": clean_value(
                row["max_endpoint_degree"]
            ),
            "mean_endpoint_degree": clean_value(
                row["mean_endpoint_degree"]
            ),
            "touches_complex_node": clean_value(
                row["touches_complex_node"]
            ),
        },
        "data_quality": {
            "speed_available": clean_value(
                row["speed_data_available"]
            ),
            "lanes_available": clean_value(
                row["lane_data_available"]
            ),
            "width_available": clean_value(
                row["width_data_available"]
            ),
            "structural_fields_available": clean_value(
                row["structural_data_fields_available"]
            ),
        },
        "model": {
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "method": MODEL_METHOD,
            "spatial_fold": spatial_fold,
        },
        "limitations": {
            "calibrated_crash_probability": False,
            "safety_certification": False,
            "traffic_exposure_controlled": False,
            "statement": (
                "Structural-context research output. "
                "A high percentile does not establish that a road "
                "is unsafe, and a low percentile does not establish "
                "that a road is safe."
            ),
        },
    }

    if distance_m is not None:
        response["query"] = {
            "distance_to_segment_m": round(float(distance_m), 2)
        }

    return response


# ---------------------------------------------------------
# Route request models
# ---------------------------------------------------------

class RoutePoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class RouteRequest(BaseModel):
    points: List[RoutePoint]


def nearest_segment(lat: float, lon: float):
    """Return nearest modeled segment and snap distance."""

    query = gpd.GeoSeries(
        [Point(lon, lat)],
        crs="EPSG:4326",
    ).to_crs("EPSG:26917").iloc[0]

    indices, distances = ROAD_SINDEX.nearest(
        query,
        return_all=False,
        return_distance=True,
    )

    if len(indices) == 0:
        return None

    tree_idx = int(indices[1][0])
    distance_m = float(distances[0])

    if distance_m > MAX_QUERY_DISTANCE_M:
        return None

    return roads_wgs84.iloc[tree_idx], distance_m


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "service": "Praedicta Road Context API",
        "company": "Praedicta Inc.",
        "positioning": "Predictive Infrastructure Intelligence",
        "version": MODEL_VERSION,
        "status": "research-preview",
        "coverage": {
            "area": "Pittsburgh, Pennsylvania, USA",
            "road_segments_loaded": len(roads_wgs84),
        },
        "purpose": (
            "Machine-readable structural road context for "
            "infrastructure, mobility, and AI applications."
        ),
        "interfaces": {
            "coordinate_context": "/v1/road-context?lat={lat}&lon={lon}",
            "segment_context": "/v1/segments/{segment_id}",
            "route_context": "/v1/route-context",
            "health": "/health",
            "interactive_documentation": "/docs",
            "openapi_schema": "/openapi.json",
        },
        "method": "Retrospective spatial out-of-fold validation",
        "interpretation": (
            "Structural context research output. Percentiles are available "
            "only for road segments inside the retrospective validation cohort."
        ),
        "limitations": {
            "calibrated_crash_probability": False,
            "safety_certification": False,
            "safe_unsafe_classification": False,
            "traffic_exposure_controlled": False,
        },
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "segments_loaded": len(roads_wgs84),
        "model_version": MODEL_VERSION,
    }


@app.get("/v1/road-context")
def road_context(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    # Query coordinate starts in WGS84.
    query = gpd.GeoSeries(
        [Point(lon, lat)],
        crs="EPSG:4326",
    ).to_crs("EPSG:26917").iloc[0]

    # GeoPandas/Shapely spatial index nearest lookup.
    nearest = ROAD_SINDEX.nearest(
        query,
        return_all=False,
        return_distance=True,
    )

    indices, distances = nearest

    if len(indices) == 0:
        raise HTTPException(
            status_code=404,
            detail="No modeled road segment found.",
        )

    # For scalar query geometry, tree index is second row.
    tree_idx = int(indices[1][0])
    distance_m = float(distances[0])

    if distance_m > MAX_QUERY_DISTANCE_M:
        raise HTTPException(
            status_code=404,
            detail={
                "message": (
                    "No modeled Pittsburgh road segment "
                    "within query distance."
                ),
                "nearest_distance_m": round(distance_m, 2),
                "maximum_distance_m": MAX_QUERY_DISTANCE_M,
            },
        )

    row = roads_wgs84.iloc[tree_idx]

    result = segment_response(
        row,
        distance_m=distance_m,
    )

    result["query"].update(
        {
            "lat": lat,
            "lon": lon,
        }
    )

    return result


@app.get("/v1/segments/{segment_id}")
def segment_by_id(segment_id: int):
    idx = SEGMENT_INDEX.get(segment_id)

    if idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"Segment {segment_id} not found.",
        )

    row = roads_wgs84.loc[idx]

    return segment_response(row)


@app.post("/v1/route-context")
def route_context(request: RouteRequest):
    """
    Enrich an externally supplied route with Praedicta
    structural road context.

    This endpoint does not calculate or optimize a route.
    """

    if len(request.points) < 2:
        raise HTTPException(
            status_code=422,
            detail="A route requires at least two points.",
        )

    if len(request.points) > 1000:
        raise HTTPException(
            status_code=422,
            detail="Maximum 1000 route points per request.",
        )

    matched = []
    unmatched_points = 0

    for point_number, point in enumerate(request.points):
        result = nearest_segment(point.lat, point.lon)

        if result is None:
            unmatched_points += 1
            continue

        row, distance_m = result
        in_cohort = bool(row["in_validation_cohort"])

        if in_cohort:
            percentile = round(
                float(row["predictive_percentile"]), 2
            )
            tier = context_tier(percentile)
            validation_scope = (
                "zero_history_2022_2023_spatial_oof"
            )
        else:
            percentile = None
            tier = None
            validation_scope = (
                "outside_zero_history_validation_cohort"
            )

        matched.append(
            {
                "point_number": point_number,
                "segment_id": int(row["segment_id"]),
                "street_name": clean_value(row["streetname"]),
                "structural_percentile": percentile,
                "tier": tier,
                "validation_scope": validation_scope,
                "in_validation_cohort": in_cohort,
                "distance_to_segment_m": round(
                    float(distance_m), 2
                ),
            }
        )

    if not matched:
        raise HTTPException(
            status_code=404,
            detail=(
                "No submitted route points matched Pittsburgh "
                "road segments within the maximum snap distance."
            ),
        )

    # Dense GPS traces can repeatedly match the same segment.
    # Keep each segment once, preserving first-observed order.
    unique_segments = []
    seen = set()

    for item in matched:
        segment_id = item["segment_id"]

        if segment_id not in seen:
            seen.add(segment_id)
            unique_segments.append(item)

    validated_segments = [
        item
        for item in unique_segments
        if item["in_validation_cohort"]
    ]

    outside_segments = [
        item
        for item in unique_segments
        if not item["in_validation_cohort"]
    ]

    percentiles = [
        item["structural_percentile"]
        for item in validated_segments
    ]

    if percentiles:
        maximum_percentile = round(max(percentiles), 2)
        mean_percentile = round(
            sum(percentiles) / len(percentiles), 2
        )

        above_80 = sum(p >= 80 for p in percentiles)
        above_90 = sum(p >= 90 for p in percentiles)
        above_95 = sum(p >= 95 for p in percentiles)
        above_99 = sum(p >= 99 for p in percentiles)
    else:
        maximum_percentile = None
        mean_percentile = None
        above_80 = 0
        above_90 = 0
        above_95 = 0
        above_99 = 0

    return {
        "route_context": {
            "points_submitted": len(request.points),
            "points_matched": len(matched),
            "points_unmatched": unmatched_points,
            "unique_segments_matched": len(unique_segments),
            "validated_segments": len(validated_segments),
            "outside_validation_cohort": len(outside_segments),
            "maximum_validated_structural_percentile":
                maximum_percentile,
            "mean_validated_structural_percentile":
                mean_percentile,
            "validated_segments_at_or_above_80th_percentile":
                above_80,
            "validated_segments_at_or_above_90th_percentile":
                above_90,
            "validated_segments_at_or_above_95th_percentile":
                above_95,
            "validated_segments_at_or_above_99th_percentile":
                above_99,
        },
        "segments": unique_segments,
        "model": {
            "name": MODEL_NAME,
            "version": MODEL_VERSION,
            "method": MODEL_METHOD,
        },
        "limitations": {
            "route_calculation": False,
            "route_optimization": False,
            "distance_weighted_analysis": False,
            "calibrated_crash_probability": False,
            "safety_certification": False,
            "traffic_exposure_controlled": False,
            "statement": (
                "Route context summarizes unique road segments "
                "matched from submitted route points. Structural "
                "percentiles are reported only for segments inside "
                "the retrospective validation cohort. Segments "
                "outside that cohort are not assigned zero risk; "
                "their validation percentile is unavailable."
            ),
        },
    }

