def test_read_resources(setup_and_fill_db, models, resources, app):
    """
    This test uses the ids of each resource to read from the database.
    """

    for resource_name, resource_list in resources.items():
        for resource in resource_list:
            r = app.get("/{}/{}".format(resource_name, resource["id"]))
            assert r.status_code == 200
