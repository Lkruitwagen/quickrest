from typing import Any


class RouterFactory:

    @classmethod
    def mount(cls, app, all_models: list[Any]):
        for model in all_models:
            model.build_models()

        base_response_models = {m.basemodel.__name__: m.basemodel for m in all_models}
        create_input_models = {
            m.create.input_model.__name__: m.create.input_model for m in all_models
        }
        patch_input_models = {
            m.patch.input_model.__name__: m.patch.input_model for m in all_models
        }
        search_input_models = {
            m.search.input_model.__name__: m.search.input_model for m in all_models
        }
        search_reponse_models = {
            m.search.response_model.__name__: m.search.response_model
            for m in all_models
        }

        all_pydantic_models = {
            **base_response_models,
            **create_input_models,
            **patch_input_models,
            **search_input_models,
            **search_reponse_models,
        }

        for model in all_models:
            model.basemodel.model_rebuild(_types_namespace=all_pydantic_models)
            model.create.input_model.model_rebuild(_types_namespace=all_pydantic_models)

        for model in all_models:
            model.build_router()

        for model in all_models:
            app.include_router(model.router)
