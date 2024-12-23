from conftest import user_headers


def test_search(setup_and_fill_db, app, USERS):
    # users can't read other users
    authorized_user = USERS["pawdrick_pupper"]
    unauthorized_user = USERS["bonita_leashley"]

    def check_search(params, pet_ids, user):
        r = app.get("/pets", params=params, headers=user_headers(user))
        assert r.status_code == 200
        for pet in r.json().get("pets"):
            assert pet.get("id") in pet_ids

    # search 1: check users can only search each others' public pets
    pet_ids = ["bacon", "mittens"]
    params = dict(public=True)
    check_search(params, pet_ids, unauthorized_user)

    # search 2: check users get their own pets regardless of public status
    pet_ids = ["waffles", "bacon"]
    params = dict(owner_id=authorized_user["id"])
    check_search(params, pet_ids, authorized_user)

    # search 3: check similarity search
    pet_ids = ["bacon"]
    params = dict(name="Bacin")
    check_search(params, pet_ids, authorized_user)

    # search 4: check vaccination date search
    pet_ids = ["mittens"]
    params = dict(vaccination_date_gte="2022-01-01")
    check_search(params, pet_ids, authorized_user)
