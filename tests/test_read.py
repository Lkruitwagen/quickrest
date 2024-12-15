from conftest import user_headers


def test_read_resources(setup_and_fill_db, models, resources, app):
    """
    This test uses the ids of each resource to read from the database.
    """

    USERS = {resource["id"]: resource for resource in resources["owners"]}

    # each user can read their own data
    for user_id, user in USERS.items():
        r = app.get(f"/owners/{user_id}", headers=user_headers(user))
        assert r.status_code == 200
        assert r.json().get("id") == user_id

        # any user can read static data
        for resource_name in ["certifications", "species"]:
            for resource in resources[resource_name]:
                _id = resource.get("id")
                r = app.get(f"/{resource_name}/{_id}", headers=user_headers(user))
                assert r.status_code == 200
                assert r.json().get("id") == _id

        # a user can read their own pets
        for pet in resources["pets"]:
            if pet["owner_id"] == user_id:
                r = app.get(f"/pets/{pet['id']}", headers=user_headers(user))
                assert r.status_code == 200
                assert r.json().get("id") == pet["id"]


def test_read_failcases(setup_and_fill_db, models, resources, app):

    USERS = {resource["id"]: resource for resource in resources["owners"]}
    PETS = {resource["id"]: resource for resource in resources["pets"]}

    # users can't read other users
    first_user, second_user = USERS["bonita_leashley"], USERS["pawdrick_pupper"]

    r = app.get(
        "/owners/{}".format(first_user["id"]), headers=user_headers(second_user)
    )
    assert r.status_code == 404

    # users can't read other users' pets

    private_pet = PETS["waffles"]
    public_pet = PETS["bacon"]

    r = app.get("/pets/{}".format(private_pet["id"]), headers=user_headers(first_user))
    assert r.status_code == 404

    # ... unless they're public
    r = app.get("/pets/{}".format(public_pet["id"]), headers=user_headers(first_user))
