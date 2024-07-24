import os
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError
from fastapi.responses import StreamingResponse
from datetime import datetime
import uuid
import io

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

app = FastAPI()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION'),
)

dynamodb = boto3.resource(
    'dynamodb',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION'),
)

# Références aux tables DynamoDB
upload_table = dynamodb.Table('FileUpload')
download_table = dynamodb.Table('FileDownload')

@app.get("/ping")
def ping():
    return "pong"

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), description: str = ""):
    try:
        # Générer un ID unique pour le fichier
        file_id = str(uuid.uuid4())
        # Obtenir la taille du fichier
        file_size = await file.read()
        file_size = len(file_size)
        file.file.seek(0)
        
        # Télécharger le fichier sur S3
        s3.upload_fileobj(file.file, os.getenv('AWS_S3_BUCKET_NAME'), file.filename)
        
        # Enregistrer les métadonnées dans DynamoDB
        upload_table.put_item(
            Item={
                'file_id': file_id,
                'filename': file.filename,
                'size': file_size,
                'description': description,
                'upload_date': datetime.utcnow().isoformat(),
                'deletion_date': None
            }
        )
        
        return {"file_id": file_id, "filename": file.filename}
    except NoCredentialsError:
        raise HTTPException(status_code=400, detail="Credentials not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_file(filename: str, request: Request):
    try:
        file_obj = io.BytesIO()
        s3.download_fileobj(os.getenv('AWS_S3_BUCKET_NAME'), filename, file_obj)
        file_obj.seek(0)

        downloader_ip = request.client.host

        download_table.put_item(
            Item={
                'id': str(uuid.uuid4()),
                'filename': filename,
                'download_date': datetime.utcnow().isoformat(),
                'downloader_ip': downloader_ip
            }
        )
        
        return StreamingResponse(file_obj, media_type='application/octet-stream')
    except NoCredentialsError:
        raise HTTPException(status_code=400, detail="Credentials not available")
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    try:
        # Rechercher l'élément dans DynamoDB en utilisant le nom du fichier
        response = upload_table.scan(
            FilterExpression="filename = :filename",
            ExpressionAttributeValues={
                ":filename": filename
            }
        )

        if 'Items' not in response or len(response['Items']) == 0:
            raise HTTPException(status_code=404, detail="File not found in DynamoDB")

        item = response['Items'][0]
        file_id = item['file_id']
        
        # Supprimer le fichier de S3
        s3.delete_object(Bucket=os.getenv('AWS_S3_BUCKET_NAME'), Key=filename)

        # Enregistrer la date de suppression dans DynamoDB
        upload_table.update_item(
            Key={'file_id': file_id},
            UpdateExpression="SET deletion_date = :deletion_date",
            ExpressionAttributeValues={
                ':deletion_date': datetime.utcnow().isoformat()
            }
        )
        
        return {"filename": filename, "status": "deleted", "delete_date": datetime.utcnow().isoformat()}
    except NoCredentialsError:
        raise HTTPException(status_code=400, detail="Credentials not available")
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files")
async def list_files():
    try:
        # Scan DynamoDB table to retrieve all files
        response = upload_table.scan(
            FilterExpression="attribute_not_exists(deletion_date) OR deletion_date = :empty",
            ExpressionAttributeValues={
                ':empty': ''
            }
        )

        # Extract file details from the response
        files = []
        for item in response.get('Items', []):
            file_info = {
                'file_id': item.get('file_id'),
                'filename': item.get('filename'),
                'size': item.get('size'),
                'upload_date': item.get('upload_date')
            }
            files.append(file_info)
        
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
