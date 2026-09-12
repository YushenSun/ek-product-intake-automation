GOOD_TEXT = "Product name: API Item\nBrand: Demo\nEAN: 4006381333931\nCategory: Home\nSupplier: Demo\nPrice: 5 EUR"


def test_api_creation_listing_and_approval(client):
    created = client.post("/products", json={"source_name": "api.txt", "text": GOOD_TEXT})
    assert created.status_code == 201
    product = created.json()
    assert product["status"] == "approved"
    assert client.get("/products").json()[0]["id"] == product["id"]
    assert client.get(f"/products/{product['id']}/export").json()["product"]["product_name"] == "API Item"
    assert client.post(f"/products/{product['id']}/approve").status_code == 200
    assert client.get("/metrics").json()["products_processed"] == 1


def test_api_rejection_and_not_found(client):
    created = client.post("/products", json={"source_name": "api.txt", "text": "Product name: Missing\nBrand: X"}).json()
    assert client.post(f"/products/{created['id']}/reject").status_code == 200
    assert client.get("/products/not-real").status_code == 404


def test_api_rejects_empty_and_unsupported_upload(client):
    assert client.post("/products", json={"source_name": "x", "text": " "}).status_code == 422
    response = client.post("/products/upload", files={"file": ("bad.exe", b"abc", "application/octet-stream")})
    assert response.status_code == 422
