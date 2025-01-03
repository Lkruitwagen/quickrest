from conftest import user_headers


def test_patch(setup_and_fill_db, app, USERS):

    # users can't read other users
    authorized_user = USERS["pawdrick_pupper"]
    unauthorized_user = USERS["bonita_leashley"]
    pet = "waffles"

    data = dict(vaccination_date="2024-12-10")

    # check users can't patch each others pets
    r = app.patch(f"/pets/{pet}", json=data, headers=user_headers(unauthorized_user))
    assert r.status_code == 404

    # check users can patch their own pets
    r = app.patch(f"/pets/{pet}", json=data, headers=user_headers(authorized_user))
    assert r.status_code == 200

    # verify pet patched
    r = app.get(f"/pets/{pet}", headers=user_headers(authorized_user))
    assert r.status_code == 200
    assert r.json().get("vaccination_date") == data["vaccination_date"]

    # patch relationship
    data_certs = dict(certifications=["dog_training_kc1", "dog_training_kc2"])

    # user patch relationship data
    r = app.patch(
        "/owners/pawdrick_pupper",
        json=data_certs,
        headers=user_headers(authorized_user),
    )
    assert r.status_code == 200

    # verify owner patched
    r = app.get("/owners/pawdrick_pupper", headers=user_headers(authorized_user))
    assert r.status_code == 200
    for cert in r.json().get("certifications"):
        assert cert.get("id") in data_certs["certifications"]
