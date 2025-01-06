def test_pop_serialize(app_types):

    authors = [
        dict(
            first_name="Ursula",
            last_name="Le Guin",
            dark_secret="She's a wizard",
        ),
        dict(
            first_name="Dan", last_name="Simmons", dark_secret="doesn't like broccoli"
        ),
    ]

    books = [
        dict(
            title="The Dispossessed",
            author_id="1",
            year=1974,
        ),
        dict(
            title="Hyperion",
            author_id="2",
            year=1989,
        ),
    ]

    # post data
    for author in authors:
        r = app_types.post("/authors", json=author)
        assert r.status_code == 201

    for book in books:
        r = app_types.post("/books", json=book)
        assert r.status_code == 201

    # read back and check no dark secrets
    r = app_types.get("/authors/1")
    assert r.status_code == 200
    assert r.json().get("first_name") == "Ursula"
    assert "dark_secret" not in r.json().keys()

    # read back and check full name
    r = app_types.get("/authors/2")
    assert r.status_code == 200
    assert r.json().get("full_name") == "Dan Simmons"

    # read back and check association proxy
    r = app_types.get("/books/1")
    assert r.status_code == 200
    assert r.json().get("author_last_name") == "Le Guin"

    # read back using int
    r = app_types.get("/books/2")
    assert r.status_code == 200
    assert r.json().get("title") == "Hyperion"


def test_uuid_read_write(app_types):

    cheeses = [
        dict(
            name="camembert",
            origin="France",
        ),
        dict(
            name="stilton",
            origin="UK",
        ),
    ]

    # post data
    cheese_ids = []
    for cheese in cheeses:
        r = app_types.post("/cheeses", json=cheese)
        assert r.status_code == 201
        cheese_ids.append(r.json().get("id"))

    # retrieve it using uuids
    for cheese, cheese_id in zip(cheeses, cheese_ids):
        r = app_types.get(f"/cheeses/{cheese_id}")
        assert r.status_code == 200
        assert r.json().get("name") == cheese["name"]


def test_uuid_slug_read_write(app_types):

    knights = [
        dict(name="Lancelot", is_round_table=True, slug="lancelot"),
        dict(name="Elton John", is_round_table=False, slug="elton-john"),
    ]

    # post data
    for knight in knights:
        r = app_types.post("/knights", json=knight)
        assert r.status_code == 201

    # retrieve it using slugs
    for knight in knights:
        r = app_types.get(f"/knights/{knight['slug']}")
        assert r.status_code == 200
        assert r.json().get("name") == knight["name"]
