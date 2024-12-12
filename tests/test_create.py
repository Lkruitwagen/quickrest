import logging


def test_create_resources(resources, app):
    """
    This test runs through all resources (in order) and makes sure they can be posted to the app
    """

    for resource_name, resource_list in resources.items():
        for resource in resource_list:
            logging.info(f"POSTING {resource_name} {resource}")
            r = app.post(f"/{resource_name}", json=resource)
            assert r.status_code == 201
