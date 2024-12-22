from conftest import user_headers


def test_delete(setup_and_fill_db, USERS, app):

    # users can't read other users
    authorized_user = USERS["pawdrick_pupper"]
    unauthorized_user = USERS["bonita_leashley"]
    pet = "waffles"

    # check users can't delete each others pets
    r = app.delete(f"/pets/{pet}", headers=user_headers(unauthorized_user))
    assert r.status_code == 404

    # check users can delete their own pets
    r = app.delete(f"/pets/{pet}", headers=user_headers(authorized_user))
    assert r.status_code == 200
    assert r.json() == 1

    # verify pet deleted
    r = app.get(f"/pets/{pet}", headers=user_headers(authorized_user))
    assert r.status_code == 404
