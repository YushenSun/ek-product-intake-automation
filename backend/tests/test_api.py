GOOD_TEXT = "Product name: API Item\nBrand: Demo\nEAN: 4006381333931\nCategory: Home\nSupplier: Demo\nPrice: 5 EUR"
BAD_TEXT = "Product name: Needs Review\nBrand: Demo\nCategory: Home\nSupplier: Demo\nPrice: 5 EUR"


def test_api_creation_listing_and_straight_through_metrics(client):
    created = client.post("/products", json={"source_name": "api.txt", "text": GOOD_TEXT})
    assert created.status_code == 201
    product = created.json()
    assert product["status"] == "approved"
    assert product["decision_source"] == "automatic"
    assert product["approval_source"] == "automatic"
    assert client.get("/products").json()[0]["id"] == product["id"]
    assert client.get(f"/products/{product['id']}/export").json()["product"]["product_name"] == "API Item"

    metrics = client.get("/metrics").json()
    assert metrics["products_processed"] == 1
    assert metrics["straight_through_approved"] == 1
    assert metrics["human_approved"] == 0
    assert metrics["historical_human_review_rate"] == 0


def test_reviewed_then_human_approved_metrics_remain_historical(client):
    created = client.post("/products", json={"source_name": "review.txt", "text": BAD_TEXT}).json()
    assert created["status"] == "review_required"

    corrected = dict(created["product"])
    corrected["ean"] = "4006381333931"
    patched = client.patch(
        f"/products/{created['id']}",
        json={"product": corrected, "reviewer_note": "Verified supplier EAN"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "ready_for_approval"
    assert patched.json()["decision_source"] == "pending_review"

    before_approval = client.get("/metrics").json()
    assert before_approval["ever_required_human_review"] == 1
    assert before_approval["currently_waiting_for_review"] == 0
    assert before_approval["ready_for_approval"] == 1
    assert before_approval["straight_through_approved"] == 0
    assert before_approval["historical_human_review_rate"] == 1

    approved = client.post(f"/products/{created['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decision_source"] == "human"
    assert approved.json()["approval_source"] == "human"

    after_approval = client.get("/metrics").json()
    assert after_approval["ever_required_human_review"] == 1
    assert after_approval["historical_human_review_rate"] == 1
    assert after_approval["human_approved"] == 1
    assert after_approval["straight_through_approved"] == 0
    assert after_approval["review_to_approval_rate"] == 1


def test_api_blocks_approval_with_errors(client):
    created = client.post("/products", json={"source_name": "bad.txt", "text": BAD_TEXT}).json()
    assert client.post(f"/products/{created['id']}/approve").status_code == 422


def test_api_rejection_and_not_found(client):
    created = client.post("/products", json={"source_name": "api.txt", "text": BAD_TEXT}).json()
    rejected = client.post(f"/products/{created['id']}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["decision_source"] == "human"
    assert client.get("/products/not-real").status_code == 404


def test_api_rejects_empty_and_unsupported_upload(client):
    assert client.post("/products", json={"source_name": "x", "text": " "}).status_code == 422
    response = client.post("/products/upload", files={"file": ("bad.exe", b"abc", "application/octet-stream")})
    assert response.status_code == 422
