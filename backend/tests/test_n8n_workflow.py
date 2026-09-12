import json
from pathlib import Path


WORKFLOW_PATH = Path(__file__).resolve().parents[2] / "n8n" / "batch_product_intake_workflow.json"


def load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_n8n_batch_workflow_has_expected_nodes_and_connections():
    workflow = load_workflow()
    nodes = {node["name"]: node for node in workflow["nodes"]}
    expected = {
        "Supplier spreadsheet webhook",
        "Validate incoming file",
        "Upload batch to FastAPI",
        "Validate batch response",
        "Fetch batch products",
        "Build outcome summary",
        "Clean straight-through?",
        "Human review involved?",
        "Partial ingestion errors?",
        "Automatic success placeholder",
        "Review notification placeholder",
        "Ingestion alert placeholder",
        "Return batch outcome",
    }

    assert expected <= nodes.keys()
    assert workflow["active"] is False
    summary_targets = {
        connection["node"]
        for connection in workflow["connections"]["Build outcome summary"]["main"][0]
    }
    assert {
        "Clean straight-through?",
        "Human review involved?",
        "Partial ingestion errors?",
        "Return batch outcome",
    } <= summary_targets


def test_n8n_batch_workflow_uses_compose_backend_and_binary_batch_endpoint():
    workflow = load_workflow()
    serialized = json.dumps(workflow)
    nodes = {node["name"]: node for node in workflow["nodes"]}
    upload = nodes["Upload batch to FastAPI"]["parameters"]
    fetch = nodes["Fetch batch products"]["parameters"]

    assert "host.docker.internal" not in serialized
    assert upload["method"] == "POST"
    assert upload["url"] == "http://backend:8000/batches/upload"
    assert upload["contentType"] == "multipart-form-data"
    assert upload["bodyParameters"]["parameters"] == [
        {
            "parameterType": "formBinaryData",
            "name": "file",
            "inputDataFieldName": "file",
        }
    ]
    assert "http://backend:8000/batches/" in fetch["url"]
    assert "/products" in fetch["url"]


def test_n8n_routes_review_and_ingestion_errors_independently():
    workflow = load_workflow()
    nodes = {node["name"]: node for node in workflow["nodes"]}
    summary_code = nodes["Build outcome summary"]["parameters"]["jsCode"]

    assert "ever_required_human_review" in summary_code
    assert "currently_review_required" in summary_code
    assert "ready_for_approval" in summary_code
    assert "failed_rows" in summary_code
    assert "humanReview" in summary_code
    assert "partialErrors" in summary_code
    assert "continueOnFail" not in json.dumps(workflow)
