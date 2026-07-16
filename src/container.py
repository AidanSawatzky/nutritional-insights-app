from azure.storage.blob import BlobServiceClient

client = BlobServiceClient.from_connection_string("UseDevelopmentStorage=true")
client.create_container("diets")
print("Done")