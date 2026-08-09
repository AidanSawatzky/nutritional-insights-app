import azure.functions as func
import pandas as pd
import io
import json
import os
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableClient
from azure.core.exceptions import ResourceNotFoundError

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="ProcessDiets", methods=["GET"])
def ProcessDiets(req: func.HttpRequest) -> func.HttpResponse:
    connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client("datasets")
    blob_client = container_client.get_blob_client("All_Diets.csv")
    stream = blob_client.download_blob().readall()
    data = pd.read_csv(io.BytesIO(stream))
    MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]
    for col in MACROS:
        data[col] = pd.to_numeric(data[col], errors="coerce")
        data[col] = data[col].fillna(data[col].mean())
    avg_macros = data.groupby("Diet_type")[MACROS].mean().round(2)
    result = {
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_recipes": len(data),
        "highest_protein_diet": avg_macros["Protein(g)"].idxmax(),
        "avg_macros_per_diet": avg_macros.reset_index().to_dict(orient="records")
    }
    return func.HttpResponse(
        json.dumps(result, indent=2),
        mimetype="application/json",
        status_code=200
    )

@app.blob_trigger(arg_name="myblob", path="datasets/All_Diets.csv", connection="AZURE_STORAGE_CONNECTION_STRING")
def CleanAndCacheResults(myblob: func.InputStream):
    connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    data = pd.read_csv(io.BytesIO(myblob.read()))
    MACROS = ["Protein(g)", "Carbs(g)", "Fat(g)"]
    for col in MACROS:
        data[col] = pd.to_numeric(data[col], errors="coerce")
        data[col] = data[col].fillna(data[col].mean())
    avg_macros = data.groupby("Diet_type")[MACROS].mean().round(2)
    result = {
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_recipes": len(data),
        "highest_protein_diet": avg_macros["Protein(g)"].idxmax(),
        "avg_macros_per_diet": avg_macros.reset_index().to_dict(orient="records")
    }
    cache_container = blob_service_client.get_container_client("cache")
    cache_container.upload_blob(name="results.json", data=json.dumps(result, indent=2), overwrite=True)
    cache_container.upload_blob(name="cleaned_diets.csv", data=data.to_csv(index=False), overwrite=True)

@app.route(route="GetResults", methods=["GET"])
def GetResults(req: func.HttpRequest) -> func.HttpResponse:
    connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    cache_container = blob_service_client.get_container_client("cache")
    blob_client = cache_container.get_blob_client("results.json")
    cached_json = blob_client.download_blob().readall()
    return func.HttpResponse(
        cached_json,
        mimetype="application/json",
        status_code=200
    )

@app.route(route="SearchRecipes", methods=["GET"])
def SearchRecipes(req: func.HttpRequest) -> func.HttpResponse:
    connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    cache_container = blob_service_client.get_container_client("cache")
    blob_client = cache_container.get_blob_client("cleaned_diets.csv")
    stream = blob_client.download_blob().readall()
    data = pd.read_csv(io.BytesIO(stream))
    diet_type = req.params.get("diet_type")
    keyword = req.params.get("keyword")
    try:
        page = max(1, int(req.params.get("page", 1)))
    except ValueError:
        page = 1
    try:
        page_size = max(1, int(req.params.get("page_size", 20)))
    except ValueError:
        page_size = 20
    if diet_type:
        data = data[data["Diet_type"].str.lower() == diet_type.lower()]
    if keyword:
        mask = (
            data["Recipe_name"].str.contains(keyword, case=False, na=False) |
            data["Cuisine_type"].str.contains(keyword, case=False, na=False)
        )
        data = data[mask]
    total_count = len(data)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = data.iloc[start:end].where(pd.notnull(data.iloc[start:end]), None)
    result = {
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": page_data.to_dict(orient="records")
    }
    return func.HttpResponse(
        json.dumps(result, indent=2, default=str),
        mimetype="application/json",
        status_code=200
    )

@app.route(route="Register", methods=["POST"])
def Register(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON body"}), status_code=400, mimetype="application/json")

    username = body.get("username")
    email = body.get("email")
    password = body.get("password")

    if not username or not email or not password:
        return func.HttpResponse(json.dumps({"error": "username, email, and password are required"}), status_code=400, mimetype="application/json")

    email = email.strip().lower()
    connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    table_client = TableClient.from_connection_string(conn_str=connect_str, table_name="Users")

    try:
        table_client.get_entity(partition_key="user", row_key=email)
        return func.HttpResponse(json.dumps({"error": "An account with this email already exists"}), status_code=409, mimetype="application/json")
    except ResourceNotFoundError:
        pass

    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000).hex()

    entity = {
        "PartitionKey": "user",
        "RowKey": email,
        "username": username,
        "password_hash": password_hash,
        "salt": salt
    }
    table_client.create_entity(entity)

    return func.HttpResponse(json.dumps({"message": "Registered successfully"}), status_code=201, mimetype="application/json")

@app.route(route="Login", methods=["POST"])
def Login(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON body"}), status_code=400, mimetype="application/json")

    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    connect_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    table_client = TableClient.from_connection_string(conn_str=connect_str, table_name="Users")

    try:
        user = table_client.get_entity(partition_key="user", row_key=email)
    except ResourceNotFoundError:
        return func.HttpResponse(json.dumps({"error": "Invalid email or password"}), status_code=401, mimetype="application/json")

    check_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(user["salt"]), 100000).hex()

    if check_hash != user["password_hash"]:
        return func.HttpResponse(json.dumps({"error": "Invalid email or password"}), status_code=401, mimetype="application/json")

    token = jwt.encode(
        {
            "email": email,
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(hours=12)
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256"
    )

    return func.HttpResponse(
        json.dumps({"token": token, "username": user["username"]}),
        status_code=200,
        mimetype="application/json"
    )