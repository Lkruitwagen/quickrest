class RouterFactory:

    @classmethod
    def mount(cls, app, all_models):
        for _name, model in all_models.items():
            model.build_models()

        base_response_models = {
            m.basemodel.__name__: m.basemodel for m in all_models.values()
        }
        create_input_models = {
            m.create.input_model.__name__: m.create.input_model
            for m in all_models.values()
        }
        patch_input_models = {
            m.patch.input_model.__name__: m.patch.input_model
            for m in all_models.values()
        }

        all_pydantic_models = {
            **base_response_models,
            **create_input_models,
            **patch_input_models,
            # **create_response_models,
            # **update_response_models,
        }

        for _name, model in all_models.items():
            model.basemodel.model_rebuild(_types_namespace=all_pydantic_models)
            model.create.input_model.model_rebuild(_types_namespace=all_pydantic_models)
            # model.create.response_model.model_rebuild(_types_namespace=all_pydantic_models)
            # model.update.input_model.model_rebuild(_types_namespace=all_pydantic_models)
            # model.update.response_model.model_rebuild(_types_namespace=all_pydantic_models)

        for _name, model in all_models.items():
            model.build_router()

        for _name, model in all_models.items():
            app.include_router(model.router)
