from io import BytesIO

from openpyxl import Workbook

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


def test_csv_batch_upload_list_detail_and_products(client):
    csv_content = (
        "Product Name,Brand,EAN,Category,Supplier,Price\n"
        "First,Demo,2000000000008,Home,Synthetic Supplier,2 EUR\n"
        "Second,Demo,2000000000015,Home,Synthetic Supplier,3 EUR\n"
    ).encode()
    response = client.post(
        "/batches/upload",
        files={"file": ("catalogue.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["status"] == "completed"
    assert batch["total_rows"] == 2
    assert batch["processed_rows"] == 2
    assert batch["straight_through_approved"] == 2

    listed = client.get("/batches")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == batch["id"]
    assert client.get(f"/batches/{batch['id']}").json()["source_name"] == "catalogue.csv"

    products = client.get(f"/batches/{batch['id']}/products")
    assert products.status_code == 200
    assert [product["source_row_number"] for product in products.json()] == [2, 3]
    assert all(product["batch_id"] == batch["id"] for product in products.json())


def test_xlsx_batch_upload(client):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Product Name", "Brand", "EAN", "Category", "Supplier", "Price"])
    sheet.append(["Sheet One", "Demo", "2000000000022", "Home", "Synthetic Supplier", "4 EUR"])
    sheet.append(["Sheet Two", "Demo", "2000000000039", "Home", "Synthetic Supplier", "5 EUR"])
    buffer = BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/batches/upload",
        files={"file": ("catalogue.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["source_type"] == "xlsx"
    assert batch["processed_rows"] == 2
    assert len(client.get(f"/batches/{batch['id']}/products").json()) == 2


def test_batch_upload_rejects_unsupported_file(client):
    response = client.post(
        "/batches/upload",
        files={"file": ("catalogue.txt", b"Product: Demo", "text/plain")},
    )
    assert response.status_code == 422
