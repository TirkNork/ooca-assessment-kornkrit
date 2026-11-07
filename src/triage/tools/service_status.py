from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from triage.repositories import ServiceStatusRepository
from triage.tools._results import error, ok


class CheckServiceStatusInput(BaseModel):
    region: str = Field(description="Service region, e.g. 'asia', 'us', 'eu'.")


def make_check_service_status(service_status: ServiceStatusRepository) -> BaseTool:
    def check_service_status(region: str) -> str:
        status = service_status.get_region(region)
        if status is None:
            known = ", ".join(service_status.regions())
            return error(f"Unknown region {region!r}. Known regions: {known}.")
        return ok(status)

    return StructuredTool.from_function(
        func=check_service_status,
        name="check_service_status",
        description=(
            "Check internal monitoring for a region: actual health, what the public status page "
            "shows, and active incidents (which may not be published yet). Use it when customers "
            "report errors, downtime or failing operations."
        ),
        args_schema=CheckServiceStatusInput,
    )
