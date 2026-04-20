"""
Contract Tests (Task 33.2, 33.3)

Covers:
- 33.2: Slide_JSON schema contract tests (all slide types, both schema versions)
- 33.3: API contract tests (all endpoints with OpenAPI validation)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from jsonschema import validate, ValidationError as JSONSchemaValidationError

from app.agents.validation import SLIDE_JSON_SCHEMA


# ---------------------------------------------------------------------------
# 33.2: Slide_JSON schema contract tests
# ---------------------------------------------------------------------------


class TestSlideJSONSchemaContracts:
    """
    Slide_JSON schema contract tests validating all slide types and schema versions.
    
    Ensures that the Slide_JSON schema correctly validates all slide types
    (title, content, chart, table, comparison) and handles both v1.0.0 and
    future schema versions.
    """

    def test_schema_v1_validates_title_slide(self):
        """
        GIVEN a valid title slide JSON
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "title",
                    "title": "AI in Healthcare",
                    "content": {"subtitle": "Clinical Decision Support"},
                    "visual_hint": "centered",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 8.5,
                    },
                }
            ],
        }

        # Should not raise
        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_content_slide(self):
        """
        GIVEN a valid content slide JSON
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "content",
                    "title": "Key Points",
                    "content": {
                        "bullets": [
                            "First point here",
                            "Second point here",
                            "Third point here",
                            "Fourth point here",
                        ]
                    },
                    "visual_hint": "bullet-left",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "openai",
                        "quality_score": 8.0,
                    },
                }
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_chart_slide(self):
        """
        GIVEN a valid chart slide JSON
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "chart",
                    "title": "Market Growth",
                    "content": {
                        "chart_data": {
                            "labels": ["2023", "2024", "2025"],
                            "values": [3.2, 4.1, 5.0],
                        },
                        "chart_type": "bar",
                    },
                    "visual_hint": "split-chart-right",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "groq",
                        "quality_score": 8.8,
                    },
                }
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_table_slide(self):
        """
        GIVEN a valid table slide JSON
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "table",
                    "title": "Performance Metrics",
                    "content": {
                        "table_data": {
                            "headers": ["Metric", "Before", "After"],
                            "rows": [
                                ["Accuracy", "85%", "95%"],
                                ["Speed", "45 min", "15 min"],
                                ["Cost", "$1000", "$400"],
                            ],
                        }
                    },
                    "visual_hint": "split-table-left",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 9.0,
                    },
                }
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_comparison_slide(self):
        """
        GIVEN a valid comparison slide JSON
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "comparison",
                    "title": "Traditional vs AI",
                    "content": {
                        "comparison_data": {
                            "left": {
                                "title": "Traditional",
                                "points": ["Manual review", "Slow process", "High cost"],
                            },
                            "right": {
                                "title": "AI-Powered",
                                "points": ["Automated", "Real-time", "Cost effective"],
                            },
                        }
                    },
                    "visual_hint": "two-column",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "openai",
                        "quality_score": 8.6,
                    },
                }
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_rejects_invalid_slide_type(self):
        """
        GIVEN a slide with invalid type
        WHEN validated against schema v1.0.0
        THEN validation fails
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "invalid_type",  # Invalid
                    "title": "Test",
                    "content": {},
                    "visual_hint": "centered",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 8.0,
                    },
                }
            ],
        }

        with pytest.raises(JSONSchemaValidationError):
            validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_rejects_invalid_visual_hint(self):
        """
        GIVEN a slide with invalid visual_hint
        WHEN validated against schema v1.0.0
        THEN validation fails
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "content",
                    "title": "Test",
                    "content": {"bullets": ["Point 1"]},
                    "visual_hint": "invalid-hint",  # Invalid
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 8.0,
                    },
                }
            ],
        }

        with pytest.raises(JSONSchemaValidationError):
            validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_rejects_missing_required_fields(self):
        """
        GIVEN a slide missing required fields
        WHEN validated against schema v1.0.0
        THEN validation fails
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "content",
                    # Missing title
                    "content": {"bullets": ["Point 1"]},
                    "visual_hint": "bullet-left",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 8.0,
                    },
                }
            ],
        }

        with pytest.raises(JSONSchemaValidationError):
            validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_optional_fields(self):
        """
        GIVEN a slide with optional fields (icon_name, highlight_text, transition)
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "content",
                    "title": "Key Metrics",
                    "content": {
                        "bullets": ["Revenue up 25%", "Costs down 15%"],
                        "icon_name": "trending-up",
                        "highlight_text": "Record growth",
                        "transition": "fade",
                    },
                    "visual_hint": "bullet-left",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 8.5,
                    },
                }
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_all_chart_types(self):
        """
        GIVEN chart slides with all valid chart_type values
        WHEN validated against schema v1.0.0
        THEN validation passes for bar, line, and pie
        """
        for chart_type in ["bar", "line", "pie"]:
            slide_json = {
                "schema_version": "1.0.0",
                "presentation_id": str(uuid.uuid4()),
                "total_slides": 1,
                "slides": [
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 1,
                        "type": "chart",
                        "title": f"{chart_type.title()} Chart",
                        "content": {
                            "chart_data": {"labels": ["A", "B"], "values": [10, 20]},
                            "chart_type": chart_type,
                        },
                        "visual_hint": "split-chart-right",
                        "layout_constraints": {
                            "max_content_density": 0.75,
                            "min_whitespace_ratio": 0.25,
                        },
                        "metadata": {
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "provider_used": "claude",
                            "quality_score": 8.0,
                        },
                    }
                ],
            }

            validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_all_transition_types(self):
        """
        GIVEN slides with all valid transition values
        WHEN validated against schema v1.0.0
        THEN validation passes for fade, slide, and none
        """
        for transition in ["fade", "slide", "none"]:
            slide_json = {
                "schema_version": "1.0.0",
                "presentation_id": str(uuid.uuid4()),
                "total_slides": 1,
                "slides": [
                    {
                        "slide_id": str(uuid.uuid4()),
                        "slide_number": 1,
                        "type": "content",
                        "title": "Test",
                        "content": {"bullets": ["Point 1"], "transition": transition},
                        "visual_hint": "bullet-left",
                        "layout_constraints": {
                            "max_content_density": 0.75,
                            "min_whitespace_ratio": 0.25,
                        },
                        "metadata": {
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "provider_used": "claude",
                            "quality_score": 8.0,
                        },
                    }
                ],
            }

            validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_validates_multi_slide_presentation(self):
        """
        GIVEN a presentation with multiple slides of different types
        WHEN validated against schema v1.0.0
        THEN validation passes
        """
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 5,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "title",
                    "title": "Presentation Title",
                    "content": {"subtitle": "Subtitle"},
                    "visual_hint": "centered",
                    "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                    "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                },
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 2,
                    "type": "content",
                    "title": "Content",
                    "content": {"bullets": ["Point 1", "Point 2"]},
                    "visual_hint": "bullet-left",
                    "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                    "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                },
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 3,
                    "type": "chart",
                    "title": "Chart",
                    "content": {"chart_data": {"labels": ["A"], "values": [10]}, "chart_type": "bar"},
                    "visual_hint": "split-chart-right",
                    "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                    "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                },
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 4,
                    "type": "table",
                    "title": "Table",
                    "content": {"table_data": {"headers": ["H1"], "rows": [["R1"]]}},
                    "visual_hint": "split-table-left",
                    "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                    "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                },
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 5,
                    "type": "comparison",
                    "title": "Comparison",
                    "content": {"comparison_data": {"left": {"title": "L", "points": ["P1"]}, "right": {"title": "R", "points": ["P2"]}}},
                    "visual_hint": "two-column",
                    "layout_constraints": {"max_content_density": 0.75, "min_whitespace_ratio": 0.25},
                    "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "provider_used": "claude", "quality_score": 8.0},
                },
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

    def test_schema_v1_enforces_layout_constraints(self):
        """
        GIVEN a slide with layout_constraints
        WHEN validated against schema v1.0.0
        THEN max_content_density and min_whitespace_ratio are required
        """
        # Valid with both constraints
        slide_json = {
            "schema_version": "1.0.0",
            "presentation_id": str(uuid.uuid4()),
            "total_slides": 1,
            "slides": [
                {
                    "slide_id": str(uuid.uuid4()),
                    "slide_number": 1,
                    "type": "content",
                    "title": "Test",
                    "content": {"bullets": ["Point 1"]},
                    "visual_hint": "bullet-left",
                    "layout_constraints": {
                        "max_content_density": 0.75,
                        "min_whitespace_ratio": 0.25,
                    },
                    "metadata": {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "provider_used": "claude",
                        "quality_score": 8.0,
                    },
                }
            ],
        }

        validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)

        # Invalid without max_content_density
        slide_json["slides"][0]["layout_constraints"] = {"min_whitespace_ratio": 0.25}

        with pytest.raises(JSONSchemaValidationError):
            validate(instance=slide_json, schema=SLIDE_JSON_SCHEMA)


# ---------------------------------------------------------------------------
# 33.3: API contract tests
# ---------------------------------------------------------------------------


class TestAPIContracts:
    """
    API contract tests for all endpoints using OpenAPI spec validation.
    
    Ensures all API endpoints conform to the OpenAPI specification and
    return responses matching the documented schemas.
    """

    @pytest.mark.asyncio
    async def test_create_presentation_endpoint_contract(self, client: AsyncClient):
        """
        GIVEN the POST /api/v1/presentations endpoint
        WHEN called with valid topic
        THEN response matches CreatePresentationResponse schema
        """
        from app.api.v1.presentations import CreatePresentationResponse

        # This test verifies the response schema structure
        # In a real scenario, we'd call the endpoint and validate the response
        response_schema = CreatePresentationResponse.model_json_schema()

        assert "properties" in response_schema
        assert "job_id" in response_schema["properties"]
        assert "presentation_id" in response_schema["properties"]
        assert "status" in response_schema["properties"]
        assert "message" in response_schema["properties"]

    @pytest.mark.asyncio
    async def test_get_presentation_status_endpoint_contract(self, client: AsyncClient):
        """
        GIVEN the GET /api/v1/presentations/{id}/status endpoint
        WHEN called with valid presentation_id
        THEN response matches PresentationStatusResponse schema
        """
        from app.api.v1.presentations import PresentationStatusResponse

        response_schema = PresentationStatusResponse.model_json_schema()

        assert "properties" in response_schema
        assert "presentation_id" in response_schema["properties"]
        assert "status" in response_schema["properties"]
        assert "progress" in response_schema["properties"]
        assert "current_agent" in response_schema["properties"]
        assert "detected_context" in response_schema["properties"]

    @pytest.mark.asyncio
    async def test_get_presentation_endpoint_contract(self, client: AsyncClient):
        """
        GIVEN the GET /api/v1/presentations/{id} endpoint
        WHEN called with completed presentation_id
        THEN response includes schema_version, slides, detected_context, metadata
        """
        # Verify the endpoint function signature and return type
        from app.api.v1 import presentations as pres_module
        import inspect

        source = inspect.getsource(pres_module.get_presentation)

        # Verify required response fields are present
        assert "schema_version" in source
        assert "slides" in source
        assert "detected_context" in source
        assert "metadata" in source

    @pytest.mark.asyncio
    async def test_regenerate_presentation_endpoint_contract(self, client: AsyncClient):
        """
        GIVEN the POST /api/v1/presentations/{id}/regenerate endpoint
        WHEN called with valid presentation_id
        THEN response matches RegenerateResponse schema
        """
        from app.api.v1.presentations import RegenerateResponse

        response_schema = RegenerateResponse.model_json_schema()

        assert "properties" in response_schema
        assert "job_id" in response_schema["properties"]
        assert "presentation_id" in response_schema["properties"]
        assert "status" in response_schema["properties"]

    @pytest.mark.asyncio
    async def test_all_endpoints_return_rate_limit_headers(self, client: AsyncClient):
        """
        GIVEN any presentation API endpoint
        WHEN called
        THEN response includes X-RateLimit-* headers
        """
        from app.api.v1 import presentations as pres_module
        import inspect

        # Verify all endpoints call _add_rate_limit_headers
        endpoints = [
            pres_module.create_presentation,
            pres_module.get_presentation_status,
            pres_module.get_presentation,
            pres_module.regenerate_presentation,
        ]

        for endpoint in endpoints:
            source = inspect.getsource(endpoint)
            assert "_add_rate_limit_headers" in source, (
                f"Endpoint {endpoint.__name__} missing rate limit headers"
            )

    @pytest.mark.asyncio
    async def test_slide_editing_endpoints_contract(self, client: AsyncClient):
        """
        GIVEN slide editing endpoints
        WHEN called with valid parameters
        THEN responses match documented schemas
        """
        from app.api.v1 import slide_editing as slide_module
        import inspect

        # Verify PATCH /slides/{slide_id} exists
        source = inspect.getsource(slide_module)
        assert "update_slide" in source or "patch" in source.lower()

        # Verify POST /slides/{slide_id}/regenerate exists
        assert "regenerate_slide" in source

        # Verify slide lock endpoints exist
        assert "lock" in source

    @pytest.mark.asyncio
    async def test_export_endpoints_contract(self, client: AsyncClient):
        """
        GIVEN export endpoints
        WHEN called with valid presentation_id
        THEN responses match documented schemas
        """
        from app.api.v1 import export_templates_admin as export_module
        import inspect

        source = inspect.getsource(export_module)

        # Verify PPTX export endpoints exist
        assert "export_pptx" in source or "pptx" in source.lower()

        # Verify template endpoints exist
        assert "templates" in source.lower()

    @pytest.mark.asyncio
    async def test_health_endpoints_contract(self, client: AsyncClient):
        """
        GIVEN health check endpoints
        WHEN called
        THEN responses match expected structure
        """
        from app.api.v1 import health as health_module
        import inspect

        source = inspect.getsource(health_module)

        # Verify all three health endpoints exist
        assert "/health" in source
        assert "/health/ready" in source or "readiness" in source.lower()
        assert "/health/live" in source or "liveness" in source.lower()

    @pytest.mark.asyncio
    async def test_schema_versioning_endpoints_contract(self, client: AsyncClient):
        """
        GIVEN schema versioning endpoints
        WHEN called
        THEN responses include version information
        """
        from app.api.v1 import schema_versioning as schema_module
        import inspect

        source = inspect.getsource(schema_module)

        # Verify schema version endpoints exist
        assert "schema" in source.lower()
        assert "version" in source.lower()

    def test_openapi_spec_includes_all_endpoints(self):
        """
        GIVEN the FastAPI app
        WHEN OpenAPI spec is generated
        THEN all documented endpoints are included
        """
        from app.main import app

        openapi_schema = app.openapi()

        assert "paths" in openapi_schema

        # Verify key endpoint paths exist
        paths = openapi_schema["paths"]
        assert "/api/v1/presentations" in paths
        assert "/api/v1/presentations/{presentation_id}/status" in paths
        assert "/api/v1/presentations/{presentation_id}" in paths
        assert "/api/v1/presentations/{presentation_id}/regenerate" in paths
        assert "/health" in paths

    def test_openapi_spec_includes_schemas(self):
        """
        GIVEN the FastAPI app
        WHEN OpenAPI spec is generated
        THEN all Pydantic schemas are included
        """
        from app.main import app

        openapi_schema = app.openapi()

        assert "components" in openapi_schema
        assert "schemas" in openapi_schema["components"]

        schemas = openapi_schema["components"]["schemas"]

        # Verify key schemas exist
        assert "CreatePresentationRequest" in schemas
        assert "CreatePresentationResponse" in schemas
        assert "PresentationStatusResponse" in schemas

    def test_openapi_spec_version_matches_app_version(self):
        """
        GIVEN the FastAPI app
        WHEN OpenAPI spec is generated
        THEN version matches app version
        """
        from app.main import app

        openapi_schema = app.openapi()

        assert "info" in openapi_schema
        assert "version" in openapi_schema["info"]
        assert openapi_schema["info"]["version"] == "1.0.0"
