"""
Visual QA Agent — post-generation visual quality assurance.

Renders PPTX slides to images, sends them to the LLM for visual inspection,
parses issues, applies fixes, and re-renders. Max 2 iterations, 60s budget.

Supports four generation modes:
- **express**: Applies heuristic fixes (trim titles, reduce bullets, change layout).
- **studio**: Sends the original ``render_code`` + issue description to the LLM
  and asks for a corrected ``render_code`` snippet (Req 10.2).
- **craft**: Code-generated slides (those with ``render_code``) use the LLM
  code-fix path; JSON-rendered slides use the existing heuristic fixes (Req 10.3).
- **artisan**: Sends the full ``artisan_code`` + issue descriptions to the LLM
  and asks for a corrected full script (Req 9.2, 9.3, 9.4).
"""
from __future__ import annotations

import time
import json
import copy
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.core.config import settings
from app.services.llm_provider import provider_factory
from app.services.streaming import streaming_service

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Visual QA Checklist — sent to the LLM alongside rendered slide images
# ---------------------------------------------------------------------------

VISUAL_QA_CHECKLIST = """\
Visually inspect these slides. Assume there are issues — find them.

Look for:
- Overlapping elements (text through shapes, lines through words, stacked elements)
- Text overflow or cut off at edges or box boundaries
- Elements too close together (less than 0.3 inch gaps)
- Uneven gaps (large empty area in one place, cramped in another)
- Insufficient margin from slide edges (less than 0.5 inch)
- Columns or similar elements not aligned consistently
- Low-contrast text (light text on light backgrounds or dark text on dark backgrounds)
- Low-contrast icons (dark icons on dark backgrounds without a contrasting circle)
- Text boxes too narrow causing excessive wrapping

For each issue found, respond in this JSON format:
{
  "issues": [
    {
      "slide_number": 1,
      "issue_type": "overlap|text_overflow|low_contrast|misalignment|spacing|wrapping|margin",
      "description": "Specific description of the issue",
      "severity": "critical|warning|info",
      "suggested_fix": "How to fix this issue"
    }
  ]
}

If no issues are found, respond with: { "issues": [] }
"""

# ---------------------------------------------------------------------------
# Code-fix prompt — sent to the LLM when a code-generated slide has issues
# ---------------------------------------------------------------------------

CODE_FIX_PROMPT = """\
You are a pptxgenjs expert. A rendered slide has visual issues that need fixing.

## Original render_code
```javascript
{render_code}
```

## Issues detected
{issues_description}

## Instructions
Produce a corrected `render_code` JavaScript function body that fixes the issues above.
The code will be executed with these variables in scope: slide, pres, theme, fonts, themes, iconToBase64.

Rules:
- Fix ONLY the reported issues — do not redesign the slide.
- Keep the same overall layout and content.
- Use theme.* for colors, fonts.* for font faces.
- Hex colors: NO '#' prefix.
- Return ONLY the corrected JavaScript code. No markdown fences, no explanation.
"""

ARTISAN_FIX_PROMPT = """\
You are a pptxgenjs expert. A presentation generated with full-script Artisan mode has visual issues that need fixing.

## Original artisan_code
```javascript
{artisan_code}
```

## Issues detected
{issues_description}

## Instructions
Produce a corrected `artisan_code` JavaScript script that fixes the issues above.
The script will be executed with these variables in scope: pres, theme, fonts, themes, iconToBase64.

Rules:
- Fix ONLY the reported issues — do not redesign the presentation.
- Keep the same overall layout, content, and slide structure.
- Use theme.* for colors, fonts.* for font faces.
- Hex colors: NO '#' prefix.
- Call pres.addSlide() to create each slide.
- Return ONLY the corrected JavaScript code. No markdown fences, no explanation.
"""

VALID_ISSUE_TYPES = frozenset({
    "overlap", "text_overflow", "low_contrast",
    "misalignment", "spacing", "wrapping", "margin",
})

VALID_SEVERITIES = frozenset({"critical", "warning", "info"})

MAX_ITERATIONS = 2
LATENCY_BUDGET_SECONDS = 60.0
PREVIEW_TIMEOUT_SECONDS = 30.0
MAX_TITLE_WORDS = 8
MAX_BULLET_COUNT = 4


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VisualQAIssue:
    slide_number: int
    issue_type: str
    description: str
    severity: str = "warning"
    fixable: bool = True
    suggested_fix: Optional[str] = None


@dataclass
class VisualQAResult:
    approved: bool
    iterations_run: int
    total_issues_found: int
    issues_fixed: int
    remaining_issues: int
    issues: List[VisualQAIssue] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "iterations_run": self.iterations_run,
            "total_issues_found": self.total_issues_found,
            "issues_fixed": self.issues_fixed,
            "remaining_issues": self.remaining_issues,
            "issues": [asdict(i) for i in self.issues],
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ---------------------------------------------------------------------------
# Visual QA Agent
# ---------------------------------------------------------------------------

class VisualQAAgent:
    """
    Post-generation visual quality assurance agent.

    1. Renders slides to JPEG via pptx-service /preview
    2. Sends images + checklist to LLM vision
    3. Parses structured issues
    4. Applies automatic fixes (trim titles, reduce bullets, change layout)
    5. Re-renders modified slides (max 2 iterations)
    6. Enforces 60-second latency budget
    """

    def __init__(self) -> None:
        self._pptx_service_url = settings.PPTX_SERVICE_URL.rstrip("/")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        slides: List[Dict[str, Any]],
        presentation_id: str,
        execution_id: str,
        design_spec: Optional[Dict[str, Any]] = None,
        theme: str = "ocean-depths",
        generation_mode: Optional["GenerationMode"] = None,
        artisan_code: Optional[str] = None,
    ) -> VisualQAResult:
        """
        Run the visual QA loop.

        Args:
            slides: List of slide dicts (Slide_JSON format).
            presentation_id: For SSE events and DB updates.
            execution_id: Pipeline execution identifier.
            design_spec: Optional design specification dict.
            theme: Theme name for rendering.
            generation_mode: Generation mode (artisan/studio/craft/express) for endpoint routing.

        Returns:
            VisualQAResult with approval status and issue details.
        """
        start = time.monotonic()
        total_issues_found = 0
        total_issues_fixed = 0
        all_issues: List[VisualQAIssue] = []
        working_slides = copy.deepcopy(slides)
        iterations_run = 0

        # Publish SSE agent_start
        try:
            await streaming_service.publish_agent_start(
                presentation_id, "visual_qa", execution_id,
                generation_mode=generation_mode.value if generation_mode else None,
            )
        except Exception:
            pass  # streaming failures must never break the pipeline

        try:
            for iteration in range(MAX_ITERATIONS):
                elapsed = time.monotonic() - start
                if elapsed >= LATENCY_BUDGET_SECONDS:
                    logger.warning(
                        "visual_qa_budget_exceeded",
                        iteration=iteration,
                        elapsed_s=round(elapsed, 1),
                    )
                    break

                iterations_run = iteration + 1

                # Determine which slides to render
                if iteration == 0:
                    render_slides = working_slides
                    slide_indices = list(range(len(working_slides)))
                else:
                    # Only re-render slides that were modified
                    render_slides = [working_slides[i] for i in modified_indices]
                    slide_indices = modified_indices  # type: ignore[possibly-undefined]

                if not render_slides:
                    break

                # Step 1: Render slides to images
                images = await self._render_slides(
                    render_slides, design_spec, theme,
                    generation_mode=generation_mode,
                    artisan_code=artisan_code,
                )
                if images is None:
                    logger.warning(
                        "visual_qa_preview_failed",
                        iteration=iteration,
                        execution_id=execution_id,
                    )
                    break

                # Step 2: Send images to LLM for inspection
                issues = await self._inspect_images(
                    images, slide_indices, execution_id,
                )
                if issues is None:
                    logger.warning(
                        "visual_qa_llm_failed",
                        iteration=iteration,
                        execution_id=execution_id,
                    )
                    break

                total_issues_found += len(issues)
                all_issues.extend(issues)

                if not issues:
                    logger.info(
                        "visual_qa_no_issues",
                        iteration=iteration,
                        execution_id=execution_id,
                    )
                    break

                logger.info(
                    "visual_qa_issues_found",
                    iteration=iteration,
                    issue_count=len(issues),
                    execution_id=execution_id,
                )

                # Step 3: Apply fixes
                fixed_count, modified_indices = await self._apply_fixes(
                    working_slides, issues,
                    generation_mode=generation_mode,
                    execution_id=execution_id,
                    design_spec=design_spec,
                    theme=theme,
                    artisan_code=artisan_code,
                )
                total_issues_fixed += fixed_count

                logger.info(
                    "visual_qa_fixes_applied",
                    iteration=iteration,
                    fixed=fixed_count,
                    modified_slides=len(modified_indices),
                    execution_id=execution_id,
                )

                if not modified_indices:
                    # No fixable issues — stop iterating
                    break

            # Copy fixed slides back
            for i, slide in enumerate(working_slides):
                slides[i] = slide

        except Exception as exc:
            logger.error(
                "visual_qa_error",
                error=str(exc),
                execution_id=execution_id,
                exc_info=True,
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        remaining = total_issues_found - total_issues_fixed
        approved = remaining == 0

        result = VisualQAResult(
            approved=approved,
            iterations_run=iterations_run,
            total_issues_found=total_issues_found,
            issues_fixed=total_issues_fixed,
            remaining_issues=remaining,
            issues=all_issues,
            elapsed_ms=elapsed_ms,
        )

        logger.info(
            "visual_qa_complete",
            approved=approved,
            iterations=iterations_run,
            total_found=total_issues_found,
            fixed=total_issues_fixed,
            remaining=remaining,
            elapsed_ms=round(elapsed_ms, 1),
            execution_id=execution_id,
        )

        # Publish SSE agent_complete
        try:
            await streaming_service.publish_agent_complete(
                presentation_id, "visual_qa", execution_id, elapsed_ms,
            )
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Step 1: Render slides to JPEG via pptx-service /preview
    # ------------------------------------------------------------------

    async def _render_slides(
        self,
        slides: List[Dict[str, Any]],
        design_spec: Optional[Dict[str, Any]],
        theme: str,
        generation_mode: Optional["GenerationMode"] = None,
        artisan_code: Optional[str] = None,
    ) -> Optional[List[str]]:
        """
        Call pptx-service /preview (or /preview-code for studio/craft modes,
        or /preview-artisan for artisan mode) to render slides as base64 JPEG
        images.

        Returns a list of base64-encoded JPEG strings, or None on failure.
        """
        from app.core.generation_mode import GenerationMode as _GM

        # Route to the correct endpoint based on generation mode
        if generation_mode == _GM.ARTISAN:
            endpoint = f"{self._pptx_service_url}/preview-artisan"
            payload: Dict[str, Any] = {
                "artisan_code": artisan_code or "",
                "theme": theme,
            }
            if design_spec:
                payload["design_spec"] = design_spec
        elif generation_mode in (_GM.STUDIO, _GM.CRAFT):
            endpoint = f"{self._pptx_service_url}/preview-code"
            payload = {
                "slides": slides,
                "theme": theme,
            }
            if design_spec:
                payload["design_spec"] = design_spec
        else:
            endpoint = f"{self._pptx_service_url}/preview"
            payload = {
                "slides": slides,
                "theme": theme,
            }
            if design_spec:
                payload["design_spec"] = design_spec

        try:
            async with httpx.AsyncClient(timeout=PREVIEW_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    endpoint,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                images = data.get("images", [])
                if not images:
                    logger.warning("visual_qa_preview_empty_images")
                    return None
                return images
        except httpx.TimeoutException:
            logger.error("visual_qa_preview_timeout")
            return None
        except Exception as exc:
            logger.error("visual_qa_preview_error", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Step 2: Send images to LLM for visual inspection
    # ------------------------------------------------------------------

    async def _inspect_images(
        self,
        images: List[str],
        slide_indices: List[int],
        execution_id: str,
    ) -> Optional[List[VisualQAIssue]]:
        """
        Send base64 JPEG images to the LLM with the visual QA checklist.

        Returns a list of VisualQAIssue objects, or None on failure.
        """
        try:
            # Build multimodal message content
            content_parts: List[Dict[str, Any]] = []

            # Add the checklist as text
            content_parts.append({
                "type": "text",
                "text": VISUAL_QA_CHECKLIST,
            })

            # Add each image
            for idx, image_b64 in enumerate(images):
                slide_num = slide_indices[idx] + 1  # 1-based
                content_parts.append({
                    "type": "text",
                    "text": f"Slide {slide_num}:",
                })
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                    },
                })

            from langchain_core.messages import HumanMessage

            message = HumanMessage(content=content_parts)

            async def _call_llm(client, msg):
                return await client.ainvoke([msg])

            response = await provider_factory.call_with_failover(
                _call_llm,
                execution_id=execution_id,
                msg=message,
            )

            return self._parse_issues(response.content)

        except Exception as exc:
            logger.error(
                "visual_qa_llm_error",
                error=str(exc),
                execution_id=execution_id,
            )
            return None

    # ------------------------------------------------------------------
    # Issue parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_issues(llm_response: str) -> List[VisualQAIssue]:
        """
        Parse the LLM response into a list of VisualQAIssue objects.

        Handles JSON embedded in markdown code blocks and plain JSON.
        Returns an empty list if parsing fails (treat as no issues).
        """
        text = llm_response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    logger.warning(
                        "visual_qa_parse_failed",
                        response_preview=text[:200],
                    )
                    return []
            else:
                logger.warning(
                    "visual_qa_no_json_found",
                    response_preview=text[:200],
                )
                return []

        raw_issues = data.get("issues", [])
        issues: List[VisualQAIssue] = []

        for item in raw_issues:
            if not isinstance(item, dict):
                continue

            slide_number = item.get("slide_number")
            issue_type = item.get("issue_type", "")
            description = item.get("description", "")

            # Validate required fields
            if not isinstance(slide_number, int) or slide_number < 1:
                continue
            if issue_type not in VALID_ISSUE_TYPES:
                continue
            if not description:
                continue

            severity = item.get("severity", "warning")
            if severity not in VALID_SEVERITIES:
                severity = "warning"

            suggested_fix = item.get("suggested_fix")

            issues.append(VisualQAIssue(
                slide_number=slide_number,
                issue_type=issue_type,
                description=description,
                severity=severity,
                fixable=_is_fixable(issue_type),
                suggested_fix=suggested_fix,
            ))

        return issues

    # ------------------------------------------------------------------
    # Step 3: Apply automatic fixes
    # ------------------------------------------------------------------

    async def _apply_fixes(
        self,
        slides: List[Dict[str, Any]],
        issues: List[VisualQAIssue],
        generation_mode: Optional["GenerationMode"] = None,
        execution_id: str = "",
        design_spec: Optional[Dict[str, Any]] = None,
        theme: str = "ocean-depths",
        artisan_code: Optional[str] = None,
    ) -> tuple[int, List[int]]:
        """
        Apply automatic fixes to slides based on detected issues.

        For artisan mode (Req 9.2, 9.3, 9.4):
        - Send the full artisan_code + issue descriptions to the LLM
        - Ask for a corrected full script
        - Pass artisan_code and design_spec to /preview-artisan for re-rendering

        For code/hybrid modes (Req 10.2, 10.3):
        - Slides with ``render_code`` → LLM-based code fix
        - Slides without ``render_code`` → existing JSON heuristic fixes

        For json mode (or when generation_mode is None):
        - All slides use existing JSON heuristic fixes

        Returns (number_of_fixes_applied, list_of_modified_slide_indices).
        """
        from app.core.generation_mode import GenerationMode as _GM

        # --- Artisan mode: full-script fix (Req 9.2, 9.3, 9.4) ---
        if generation_mode == _GM.ARTISAN:
            if artisan_code:
                fixed_count, modified_indices = await self._apply_artisan_fixes(
                    slides, issues, artisan_code, design_spec, theme, execution_id,
                )
                return fixed_count, modified_indices
            else:
                logger.warning(
                    "visual_qa_artisan_no_code",
                    execution_id=execution_id,
                )
                return 0, []

        is_code_aware = generation_mode in (_GM.STUDIO, _GM.CRAFT)

        # Partition issues into code-slide issues and json-slide issues
        code_issues: Dict[int, List[VisualQAIssue]] = {}  # idx → issues
        json_issues: List[VisualQAIssue] = []

        for issue in issues:
            idx = issue.slide_number - 1
            if idx < 0 or idx >= len(slides):
                continue

            slide = slides[idx]
            if is_code_aware and slide.get("render_code"):
                code_issues.setdefault(idx, []).append(issue)
            else:
                json_issues.append(issue)

        fixed_count = 0
        modified_indices: set[int] = set()

        # --- Code-slide fixes via LLM (Req 10.2) ---
        if code_issues:
            code_fixed, code_modified = await self._apply_code_fixes(
                slides, code_issues, execution_id,
            )
            fixed_count += code_fixed
            modified_indices.update(code_modified)

        # --- JSON-slide fixes via heuristics (Req 10.3) ---
        if json_issues:
            json_fixed, json_modified = _apply_json_fixes(slides, json_issues)
            fixed_count += json_fixed
            modified_indices.update(json_modified)

        return fixed_count, sorted(modified_indices)

    # ------------------------------------------------------------------
    # Artisan-script fix: ask LLM for corrected full script (Req 9.2, 9.3, 9.4)
    # ------------------------------------------------------------------

    async def _apply_artisan_fixes(
        self,
        slides: List[Dict[str, Any]],
        issues: List[VisualQAIssue],
        artisan_code: str,
        design_spec: Optional[Dict[str, Any]],
        theme: str,
        execution_id: str,
    ) -> tuple[int, List[int]]:
        """
        For Artisan mode, send the full artisan_code + issue descriptions to the LLM
        and ask for a corrected full script (Req 9.2).

        Pass the corrected artisan_code and design_spec to /preview-artisan for
        re-rendering (Req 9.3).

        Returns (fixes_applied, modified_indices).
        """
        if not issues:
            return 0, []

        # Build issue description block
        issues_desc = "\n".join(
            f"- [{issue.severity}] Slide {issue.slide_number}: {issue.issue_type}: {issue.description}"
            + (f" (suggested: {issue.suggested_fix})" if issue.suggested_fix else "")
            for issue in issues
        )

        corrected_code = await self._get_corrected_artisan_code(
            artisan_code, issues_desc, execution_id,
        )

        if corrected_code and corrected_code != artisan_code:
            # Update the artisan_code in slides (stored as {"artisan_code": "..."})
            if slides and isinstance(slides[0], dict) and "artisan_code" in slides[0]:
                slides[0]["artisan_code"] = corrected_code
            
            logger.info(
                "visual_qa_artisan_fix_applied",
                issue_count=len(issues),
                execution_id=execution_id,
            )
            # For artisan mode, we consider all slides as modified since the entire
            # script was regenerated
            return 1, list(range(len(slides)))
        else:
            # LLM could not produce a fix — mark issues as not fixable
            for issue in issues:
                issue.fixable = False
            logger.warning(
                "visual_qa_artisan_fix_failed",
                issue_count=len(issues),
                execution_id=execution_id,
            )
            return 0, []

    async def _get_corrected_artisan_code(
        self,
        original_code: str,
        issues_description: str,
        execution_id: str,
    ) -> Optional[str]:
        """
        Call the LLM to produce corrected artisan_code for the full presentation.

        Returns the corrected code string, or None on failure.
        """
        prompt_text = ARTISAN_FIX_PROMPT.format(
            artisan_code=original_code,
            issues_description=issues_description,
        )

        try:
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content=prompt_text)

            async def _call_llm(client, msg):
                return await client.ainvoke([msg])

            response = await provider_factory.call_with_failover(
                _call_llm,
                execution_id=execution_id,
                msg=message,
            )

            corrected = response.content.strip()

            # Strip markdown code fences if the LLM wrapped the output
            if corrected.startswith("```"):
                lines = corrected.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                corrected = "\n".join(lines).strip()

            # Basic sanity: must contain at least one pres.addSlide() call
            if "pres.addSlide()" not in corrected:
                logger.warning(
                    "visual_qa_artisan_fix_no_add_slide",
                    code_preview=corrected[:200],
                )
                return None

            return corrected

        except Exception as exc:
            logger.error(
                "visual_qa_artisan_fix_llm_error",
                error=str(exc),
                execution_id=execution_id,
            )
            return None



    async def _apply_code_fixes(
        self,
        slides: List[Dict[str, Any]],
        code_issues: Dict[int, List[VisualQAIssue]],
        execution_id: str,
    ) -> tuple[int, List[int]]:
        """
        For each slide index with issues, send the original render_code and
        issue descriptions to the LLM and ask for a corrected render_code.

        Returns (fixes_applied, modified_indices).
        """
        fixed_count = 0
        modified_indices: List[int] = []

        for idx, issues in code_issues.items():
            slide = slides[idx]
            original_code = slide.get("render_code", "")
            if not original_code:
                for issue in issues:
                    issue.fixable = False
                continue

            # Build issue description block
            issues_desc = "\n".join(
                f"- [{issue.severity}] {issue.issue_type}: {issue.description}"
                + (f" (suggested: {issue.suggested_fix})" if issue.suggested_fix else "")
                for issue in issues
            )

            corrected_code = await self._get_corrected_code(
                original_code, issues_desc, execution_id,
            )

            if corrected_code and corrected_code != original_code:
                slide["render_code"] = corrected_code
                fixed_count += 1
                modified_indices.append(idx)
                logger.info(
                    "visual_qa_code_fix_applied",
                    slide_index=idx,
                    issue_count=len(issues),
                    execution_id=execution_id,
                )
            else:
                # LLM could not produce a fix — mark issues as not fixable
                for issue in issues:
                    issue.fixable = False
                logger.warning(
                    "visual_qa_code_fix_failed",
                    slide_index=idx,
                    issue_count=len(issues),
                    execution_id=execution_id,
                )

        return fixed_count, modified_indices

    async def _get_corrected_code(
        self,
        original_code: str,
        issues_description: str,
        execution_id: str,
    ) -> Optional[str]:
        """
        Call the LLM to produce corrected render_code for a single slide.

        Returns the corrected code string, or None on failure.
        """
        prompt_text = CODE_FIX_PROMPT.format(
            render_code=original_code,
            issues_description=issues_description,
        )

        try:
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content=prompt_text)

            async def _call_llm(client, msg):
                return await client.ainvoke([msg])

            response = await provider_factory.call_with_failover(
                _call_llm,
                execution_id=execution_id,
                msg=message,
            )

            corrected = response.content.strip()

            # Strip markdown code fences if the LLM wrapped the output
            if corrected.startswith("```"):
                lines = corrected.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                corrected = "\n".join(lines).strip()

            # Basic sanity: must contain at least one pptxgenjs API call
            pptx_patterns = (
                "slide.addText", "slide.addShape", "slide.addChart",
                "slide.addImage", "slide.addTable", "slide.background",
            )
            if not any(p in corrected for p in pptx_patterns):
                logger.warning(
                    "visual_qa_code_fix_no_pptx_call",
                    code_preview=corrected[:200],
                )
                return None

            return corrected

        except Exception as exc:
            logger.error(
                "visual_qa_code_fix_llm_error",
                error=str(exc),
                execution_id=execution_id,
            )
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_fixable(issue_type: str) -> bool:
    """Determine if an issue type is potentially auto-fixable."""
    return issue_type in (
        "text_overflow", "wrapping", "spacing",
        "overlap", "misalignment", "margin",
    )


def _apply_json_fixes(
    slides: List[Dict[str, Any]],
    issues: List[VisualQAIssue],
) -> tuple[int, List[int]]:
    """
    Apply heuristic fixes to JSON-rendered slides (no ``render_code``).

    Fixes include trimming long titles, reducing bullet counts, and
    switching to simpler layout variants.

    Returns (number_of_fixes_applied, list_of_modified_slide_indices).
    """
    fixed_count = 0
    modified_indices: set[int] = set()

    for issue in issues:
        idx = issue.slide_number - 1  # Convert to 0-based
        if idx < 0 or idx >= len(slides):
            continue

        slide = slides[idx]
        content = slide.get("content", {})

        applied = False

        if issue.issue_type in ("text_overflow", "wrapping", "spacing"):
            # Fix 1: Trim long titles (> MAX_TITLE_WORDS words)
            title = slide.get("title", "")
            words = title.split()
            if len(words) > MAX_TITLE_WORDS:
                slide["title"] = " ".join(words[:MAX_TITLE_WORDS])
                applied = True

            # Fix 2: Reduce bullet count (> MAX_BULLET_COUNT)
            bullets = content.get("bullets", [])
            if len(bullets) > MAX_BULLET_COUNT:
                content["bullets"] = bullets[:MAX_BULLET_COUNT]
                applied = True

        elif issue.issue_type in ("overlap", "misalignment"):
            # Fix 3: Change layout_variant to reduce complexity
            slide_type = slide.get("slide_type", "content")
            current_variant = slide.get("layout_variant", "")

            new_variant = _get_simpler_variant(slide_type, current_variant)
            if new_variant and new_variant != current_variant:
                slide["layout_variant"] = new_variant
                applied = True

            # Also trim long titles for overlap issues
            title = slide.get("title", "")
            words = title.split()
            if len(words) > MAX_TITLE_WORDS:
                slide["title"] = " ".join(words[:MAX_TITLE_WORDS])
                applied = True

        elif issue.issue_type == "margin":
            # Trim title and reduce bullets to give more margin space
            title = slide.get("title", "")
            words = title.split()
            if len(words) > MAX_TITLE_WORDS:
                slide["title"] = " ".join(words[:MAX_TITLE_WORDS])
                applied = True

            bullets = content.get("bullets", [])
            if len(bullets) > MAX_BULLET_COUNT:
                content["bullets"] = bullets[:MAX_BULLET_COUNT]
                applied = True

        # low_contrast is not auto-fixable (requires theme/color changes)
        if not applied:
            issue.fixable = False

        if applied:
            fixed_count += 1
            modified_indices.add(idx)

    return fixed_count, sorted(modified_indices)


# Default (simpler) layout variants per slide type
_SIMPLER_VARIANTS: Dict[str, str] = {
    "content": "numbered-cards",
    "chart": "chart-right",
    "table": "table-full",
    "comparison": "two-column",
}


def _get_simpler_variant(
    slide_type: str, current_variant: str,
) -> Optional[str]:
    """Return a simpler layout variant for the given slide type."""
    default = _SIMPLER_VARIANTS.get(slide_type)
    if default and default != current_variant:
        return default
    return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

visual_qa_agent = VisualQAAgent()
