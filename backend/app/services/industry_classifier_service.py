"""
Industry Classifier Service

Service layer for Industry Classifier Agent that handles database persistence
and integration with the presentation pipeline.
"""

from typing import Optional
from uuid import UUID
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.industry_classifier import industry_classifier, DetectedContext
from app.db.models import Presentation, Template


logger = structlog.get_logger(__name__)


class IndustryClassifierService:
    """
    Service for running Industry Classifier Agent and persisting results
    """
    
    async def classify_and_store(
        self,
        db: AsyncSession,
        presentation_id: UUID,
        topic: str,
        execution_id: str,
    ) -> DetectedContext:
        """
        Run industry classification and store results on presentation record
        
        Args:
            db: Database session
            presentation_id: Presentation ID to update
            topic: User-provided topic
            execution_id: Unique execution ID for tracing
        
        Returns:
            DetectedContext with classification results
        """
        logger.info(
            "classifying_industry",
            presentation_id=str(presentation_id),
            topic=topic[:100],
            execution_id=execution_id,
        )
        
        # Run classification
        context = await industry_classifier.classify(topic, execution_id)
        
        # Resolve template ID from template name
        template_id = await self._resolve_template_id(
            db,
            context.selected_template_name,
            context.industry,
        )
        
        # Update context with resolved template ID
        context.selected_template_id = str(template_id) if template_id else None
        
        # Store on presentation record
        await self._store_context(db, presentation_id, context)
        
        logger.info(
            "industry_classification_stored",
            presentation_id=str(presentation_id),
            industry=context.industry,
            confidence=context.confidence,
            template=context.selected_template_name,
            execution_id=execution_id,
        )
        
        return context
    
    async def _resolve_template_id(
        self,
        db: AsyncSession,
        template_name: str,
        industry: str,
    ) -> Optional[UUID]:
        """
        Resolve template ID from template name and industry
        
        Args:
            db: Database session
            template_name: Template name to resolve
            industry: Industry for template lookup
        
        Returns:
            Template UUID if found, None otherwise
        """
        try:
            # Query for system template matching name and industry
            stmt = select(Template).where(
                Template.name == template_name,
                Template.industry == industry,
                Template.is_system == True,
            )
            
            result = await db.execute(stmt)
            template = result.scalar_one_or_none()
            
            if template:
                logger.info(
                    "template_resolved",
                    template_name=template_name,
                    template_id=str(template.id),
                    industry=industry,
                )
                return template.id
            
            # Try fallback: match by name only
            stmt = select(Template).where(
                Template.name == template_name,
                Template.is_system == True,
            )
            
            result = await db.execute(stmt)
            template = result.scalar_one_or_none()
            
            if template:
                logger.info(
                    "template_resolved_fallback",
                    template_name=template_name,
                    template_id=str(template.id),
                )
                return template.id
            
            logger.warning(
                "template_not_found",
                template_name=template_name,
                industry=industry,
            )
            return None
            
        except Exception as e:
            logger.error(
                "template_resolution_failed",
                template_name=template_name,
                error=str(e),
            )
            return None
    
    async def _store_context(
        self,
        db: AsyncSession,
        presentation_id: UUID,
        context: DetectedContext,
    ) -> None:
        """
        Store DetectedContext on presentation record
        
        Args:
            db: Database session
            presentation_id: Presentation ID to update
            context: DetectedContext to store
        """
        try:
            # Get presentation
            stmt = select(Presentation).where(
                Presentation.presentation_id == presentation_id
            )
            result = await db.execute(stmt)
            presentation = result.scalar_one_or_none()
            
            if not presentation:
                logger.error(
                    "presentation_not_found",
                    presentation_id=str(presentation_id),
                )
                raise ValueError(f"Presentation {presentation_id} not found")
            
            # Update presentation with detected context
            presentation.detected_industry = context.industry
            presentation.detection_confidence = context.confidence
            presentation.detected_sub_sector = context.sub_sector
            presentation.inferred_audience = context.target_audience
            
            # Resolve template ID if available
            if context.selected_template_id:
                try:
                    presentation.selected_template_id = UUID(context.selected_template_id)
                except (ValueError, TypeError):
                    logger.warning(
                        "invalid_template_id",
                        template_id=context.selected_template_id,
                    )
            
            presentation.selected_theme = context.theme
            presentation.compliance_context = context.compliance_context
            
            # Commit changes
            await db.commit()
            await db.refresh(presentation)
            
            logger.info(
                "context_stored",
                presentation_id=str(presentation_id),
                industry=context.industry,
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(
                "context_storage_failed",
                presentation_id=str(presentation_id),
                error=str(e),
            )
            raise
    
    async def get_detected_context(
        self,
        db: AsyncSession,
        presentation_id: UUID,
    ) -> Optional[DetectedContext]:
        """
        Retrieve DetectedContext from presentation record
        
        Args:
            db: Database session
            presentation_id: Presentation ID
        
        Returns:
            DetectedContext if available, None otherwise
        """
        try:
            stmt = select(Presentation).where(
                Presentation.presentation_id == presentation_id
            )
            result = await db.execute(stmt)
            presentation = result.scalar_one_or_none()
            
            if not presentation or not presentation.detected_industry:
                return None
            
            # Reconstruct DetectedContext from presentation fields
            context = DetectedContext(
                industry=presentation.detected_industry,
                confidence=presentation.detection_confidence or 0.0,
                sub_sector=presentation.detected_sub_sector,
                target_audience=presentation.inferred_audience or "general",
                selected_template_id=str(presentation.selected_template_id) if presentation.selected_template_id else None,
                selected_template_name="",  # Would need to join with Template to get name
                theme=presentation.selected_theme or "deloitte",
                compliance_context=presentation.compliance_context or [],
                classification_method="",  # Not stored in DB
            )
            
            return context
            
        except Exception as e:
            logger.error(
                "context_retrieval_failed",
                presentation_id=str(presentation_id),
                error=str(e),
            )
            return None


# Global service instance
industry_classifier_service = IndustryClassifierService()
