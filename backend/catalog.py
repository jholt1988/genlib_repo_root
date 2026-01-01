from fastapi import APIRouter
router = APIRouter()

@router.get("/")
def catalog():
    return {"items":[]}
