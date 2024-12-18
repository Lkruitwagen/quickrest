import logging

from conftest import user_headers


def test_create_resources(resources, app, superuser_headers, admin_user_id):
    """
    This test runs through all resources (in order) and makes sure they can be posted to the app
    """

    USERS = {resource["id"]: resource for resource in resources["owners"]}

    # post static and types
    for resource_name in ["certifications", "species"]:
        for resource in resources[resource_name]:
            logging.info(f"POSTING {resource_name} {resource}")
            r = app.post(
                f"/{resource_name}",
                json=resource,
                headers=user_headers(USERS[admin_user_id]),
            )
            assert r.status_code == 201

    # post users
    for resource in USERS.values():
        logging.info(f"POSTING owners {resource}")
        r = app.post("/owners", json=resource, headers=superuser_headers)
        assert r.status_code == 201

    # post data
    for resource_name in ["pets"]:
        for resource in resources[resource_name]:
            logging.info(f"POSTING {resource_name} {resource}")
            r = app.post(
                f"/{resource_name}",
                json=resource,
                headers=user_headers(USERS[resource["owner_id"]]),
            )
            assert r.status_code == 201


def test_create_fail_on_dependencies(
    resources, app, superuser_headers, admin_user_id, nonadmin_user_id
):
    """
    This test checks that global dependency injection is working correctly
    """

    USERS = {resource["id"]: resource for resource in resources["owners"]}

    # static types are protected 'admin only'
    for resource_name in ["certifications", "species"]:
        for resource in resources[resource_name]:
            logging.info(f"POSTING {resource_name} {resource}")
            r = app.post(
                f"/{resource_name}",
                json=resource,
                headers=user_headers(USERS[nonadmin_user_id]),
            )
            assert r.status_code == 401

    # users are protected 'superuser only'
    for resource in USERS.values():
        logging.info(f"POSTING owners {resource}")
        r = app.post(
            "/owners", json=resource, headers=user_headers(USERS[admin_user_id])
        )
        assert r.status_code == 401
