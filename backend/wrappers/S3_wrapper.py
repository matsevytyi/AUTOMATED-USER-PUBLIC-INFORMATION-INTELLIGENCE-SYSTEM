import boto3
from botocore.exceptions import ClientError
import os

from dotenv import load_dotenv
load_dotenv()

#profolio-thesis-main

# Access config
S3_BUCKET_NAME = "profolio-thesis-main"

S3_PREFIX = ""
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

AWS_REGION='eu-west-1'

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url='https://xabvynnhatnxrtewbncz.storage.supabase.co/storage/v1/s3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
    )

print("AWS client established successfully")


# Functions
def upload_file_to_s3(local_file_path, s3_key=None):
    """Upload a file to S3 bucket"""
    if s3_key is None:
        s3_key = S3_PREFIX + os.path.basename(local_file_path)
    
    try:
        s3_client.upload_file(local_file_path, S3_BUCKET_NAME, s3_key)
        print("Loaded file to S3 successfully:", s3_key)
        return f"s3://{S3_BUCKET_NAME}/{s3_key}"
    except ClientError as e:
        print(f"Error uploading file to S3: {e}")
        return None

def download_file_from_s3(s3_key, local_file_path):
    """Download a file from S3 bucket"""
    try:
        s3_client.download_file(S3_BUCKET_NAME, s3_key, local_file_path)
        return True
    except ClientError as e:
        print(f"Error downloading file from S3: {e}")
        return False

def list_files_in_s3():
    """List all PDF files in the S3 bucket/prefix"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=S3_PREFIX
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'].endswith('.pdf'):
                    files.append(obj['Key'])
        return files
    except ClientError as e:
        print(f"Error listing files in S3: {e}")
        return []

def get_total_size_in_s3():
    """Get total size of all files in S3 bucket/prefix in bytes"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=S3_PREFIX
        )
        
        total_size = 0
        if 'Contents' in response:
            for obj in response['Contents']:
                total_size += obj['Size']
        return total_size
    except ClientError as e:
        print(f"Error getting total size in S3: {e}")
        return 0

def delete_file_from_s3(s3_key):
    """Delete a file from S3 bucket"""
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError as e:
        print(f"Error deleting file from S3: {e}")
        return False


if __name__ == "__main__":
    upload_file_to_s3("backend/test_file.pdf")
    print("files:", list_files_in_s3())
    print(list_files_in_s3())
    response = s3_client.list_buckets()
    print([bucket['Name'] for bucket in response['Buckets']])
    print([bucket['Name'] for bucket in response['Buckets']])