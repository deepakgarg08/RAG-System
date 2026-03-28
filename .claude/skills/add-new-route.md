# Skill: Add a New API Route

## When to use this skill
Use when adding a new HTTP endpoint to the FastAPI backend.

## Step-by-step process

### 1. Read first
Read backend/app/api/routes/README.md before writing anything.
Remember: routes contain NO business logic — they only validate input and delegate.

### 2. Create the route file
Create: `backend/app/api/routes/<name>.py`

Template to follow:
```python
"""
<name>.py — <one sentence describing what this route does>
Delegates to: <which service/module does the actual work>
"""
from fastapi import APIRouter, HTTPException
from app.models import <RequestModel>, <ResponseModel>
from app.<service> import <service_function>

router = APIRouter()

@router.post("/<path>", response_model=<ResponseModel>)
async def <handler_name>(<request>: <RequestModel>):
    """<docstring explaining endpoint behaviour>"""
    try:
        result = await <service_function>(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error")
```

### 3. Add request/response models
Add Pydantic models to `backend/app/models.py` for the new endpoint.

### 4. Register the router
In `backend/app/main.py`, import and include the new router:
```python
from app.api.routes.<name> import router as <name>_router
app.include_router(<name>_router, prefix="/api")
```

### 5. Write tests
Add endpoint tests to `backend/tests/` using pytest and httpx AsyncClient.

### 6. Update docs
Update `backend/app/api/routes/README.md` with the new endpoint description.
