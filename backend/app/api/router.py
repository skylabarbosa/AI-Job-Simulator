from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.blueprints import router as blueprints_router
from app.api.routes.simulations import router as simulations_router
from app.api.routes.submissions import router as submissions_router
from app.api.routes.performance import router as performance_router
from app.api.routes.learner import router as learner_router
from app.api.routes.adaptive import router as adaptive_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(projects_router)
api_router.include_router(datasets_router)
api_router.include_router(blueprints_router)
api_router.include_router(simulations_router)
api_router.include_router(submissions_router)
api_router.include_router(performance_router)
api_router.include_router(learner_router)
api_router.include_router(adaptive_router)
