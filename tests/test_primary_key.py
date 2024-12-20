def test_int_read_write(app_types):

    books = [
        dict(
            title="The Dispossessed",
            author="Ursula K. Le Guin",
            year=1974,
        ),
        dict(
            title="Hyperion",
            author="Dan Simmons",
            year=1989,
        ),
    ]

    # post data
    for book in books:
        r = app_types.post("/books", json=book)
        assert r.status_code == 201

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
