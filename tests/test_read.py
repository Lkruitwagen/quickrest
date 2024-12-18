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


def test_read_serialized_attribute(setup_and_fill_db, models, resources, app):

    user_id = "bonita_leashley"
    certification_ids = ["dog_training_kc1", "dog_training_kc2"]

    USERS = {resource["id"]: resource for resource in resources["owners"]}

    r = app.get(f"/owners/{user_id}", headers=user_headers(USERS[user_id]))
    assert r.status_code == 200
    assert r.json().get("id") == user_id
    assert isinstance(r.json().get("certifications"), list)
    for cert in r.json().get("certifications"):
        assert cert["id"] in certification_ids
    assert r.json().get("certifications")[0]["description"]


def test_read_routed_relationship(setup_and_fill_db, models, resources, app):
    """
    This test uses the ids of each resource to read from the database.
    """

    USERS = {resource["id"]: resource for resource in resources["owners"]}
    PETS = {resource["id"]: resource for resource in resources["pets"]}

    user_id = "pawdrick_pupper"
    user_pets = {k: v for k, v in PETS.items() if v["owner_id"] == user_id}

    r = app.get(f"/owners/{user_id}/pets", headers=user_headers(USERS[user_id]))
    assert r.status_code == 200
    assert len(r.json()) == len(user_pets)
    for pet in r.json():
        assert pet["owner_id"] == user_id
        assert pet["id"] in user_pets
        assert pet["name"] == user_pets[pet["id"]]["name"]
