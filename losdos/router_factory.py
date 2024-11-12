class RouterFactory:

    @classmethod
    def mount(cls, app, all_models):
        for _name, model in all_models.items():
            model.build_models()

        all_pydanic_models = {
            m.read.response_model.__name__: m.read.response_model
            for m in all_models.values()
        }

        for _name, model in all_models.items():
            model.read.response_model.model_rebuild(_types_namespace=all_pydanic_models)

        for _name, model in all_models.items():
            model.build_router()

        for _name, model in all_models.items():
            app.include_router(model.router)
