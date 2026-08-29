"""Router for Form 16 document summarization."""

from fastapi import APIRouter, File, UploadFile
from app.document.form16 import summarise_form16_upload
from app.schemas.api import Form16SummaryResponse

router = APIRouter(prefix="/form16", tags=["form16"])


@router.post("/summary", response_model=Form16SummaryResponse)
async def form16_summary_endpoint(file: UploadFile = File(...)):
    """Extract, parse, and generate an explainable plain-English summary of an uploaded Form 16 PDF."""
    result = await summarise_form16_upload(file)
    return Form16SummaryResponse(
        summary=result["summary"],
        summary_source=result["summary_source"],
        key_figures=result["key_figures"],
        explainers=result["explainers"],
        warnings=result["warnings"],
        retrieved_chunks=result["retrieved_chunks"],
    )
 