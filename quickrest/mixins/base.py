from abc import ABC, abstractmethod

from fastapi import Depends


class BaseMixin:
    pass


class RESTFactory(ABC):

    @classmethod
    @abstractmethod
    def controller_factory(cls) -> callable: ...  # noqa: E704

    def attach_route(self, model) -> None:

        model.router.add_api_route(
            self.ROUTE,
            self.controller,
            description=getattr(model, self.CFG_NAME).description,
            dependencies=[
                Depends(d) for d in getattr(model, self.CFG_NAME).dependencies
            ],
            summary=getattr(model, self.CFG_NAME).summary,
            tags=getattr(model, self.CFG_NAME).tags,
            operation_id=getattr(model, self.CFG_NAME).operation_id,
            methods=[self.METHOD],
            status_code=getattr(self, "SUCCESS_CODE", None) or 200,
            response_model=getattr(self, "response_model", model.basemodel),
        )
