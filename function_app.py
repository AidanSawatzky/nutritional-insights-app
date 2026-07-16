import azure.functions as func
import pandas as pd
import io
import json
import os
from datetime import datetime
from azure.storage.blob import BlobServiceClient

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