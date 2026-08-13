"""POST /query — ask a question, optionally in the context of a selected parcel."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.orchestrator import answer
from app.agents.planner_agent import PlanAgentError
from app.llm.openrouter_client import LLMError

router = APIRouter()


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    apn: str | None = None
    # Raw attributes from the clicked map feature. Sent per request rather than
    # stored, so two users can never see each other's parcel.
    parcel_attributes: dict | None = None


@router.post("/query")
def query(body: QueryRequest):
    # Sync def: the agent chain uses `requests`, which blocks. FastAPI runs this
    # in a threadpool so the event loop stays free.
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        return answer(
            question=body.question,
            apn=body.apn,
            parcel_attributes=body.parcel_attributes,
        )
    except PlanAgentError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except LLMError as err:
        # Upstream model problem, not ours.
        raise HTTPException(status_code=502, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Query failed: {err}") from err
