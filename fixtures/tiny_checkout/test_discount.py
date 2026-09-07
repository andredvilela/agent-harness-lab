from discount import apply_percentage_discount


def test_percentage_discount():
    assert apply_percentage_discount(200.0, 10.0) == 180.0
