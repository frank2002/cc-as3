import json
import boto3
import os
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Initialize AWS clients
s3_client = boto3.client('s3')
rekognition_client = boto3.client('rekognition')

# OpenSearch configuration
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')
OPENSEARCH_REGION = os.environ.get('AWS_REGION', 'us-east-1')
OPENSEARCH_INDEX = 'photos'

def get_opensearch_client():
    """Create OpenSearch client with AWS authentication"""
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        OPENSEARCH_REGION,
        'es',
        session_token=credentials.token
    )

    # Remove https:// prefix if present
    host = OPENSEARCH_ENDPOINT.replace('https://', '').replace('http://', '')

    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client

def lambda_handler(event, context):
    """
    Lambda function to index photos in OpenSearch when uploaded to S3

    Workflow:
    1. Extract S3 event information
    2. Detect labels using AWS Rekognition
    3. Retrieve custom labels from S3 object metadata
    4. Store photo metadata in OpenSearch
    """

    try:
        print(f"Received event: {json.dumps(event)}")

        # Extract S3 bucket and object key from event
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']

            print(f"Processing file: {key} from bucket: {bucket}")

            # Step 1: Detect labels using Rekognition
            labels = []
            try:
                rekognition_response = rekognition_client.detect_labels(
                    Image={
                        'S3Object': {
                            'Bucket': bucket,
                            'Name': key
                        }
                    },
                    MaxLabels=10,
                    MinConfidence=75
                )

                # Extract label names
                for label in rekognition_response['Labels']:
                    labels.append(label['Name'].lower())

                print(f"Rekognition detected labels: {labels}")

            except Exception as e:
                print(f"Error detecting labels with Rekognition: {str(e)}")

            # Step 2: Retrieve custom labels from S3 metadata
            try:
                head_response = s3_client.head_object(Bucket=bucket, Key=key)
                metadata = head_response.get('Metadata', {})

                custom_labels_str = metadata.get('customlabels', '')
                if custom_labels_str:
                    # Split by comma and clean up
                    custom_labels = [label.strip().lower() for label in custom_labels_str.split(',') if label.strip()]
                    labels.extend(custom_labels)
                    print(f"Custom labels found: {custom_labels}")

            except Exception as e:
                print(f"Error retrieving S3 metadata: {str(e)}")

            # Step 3: Create document for OpenSearch
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

            document = {
                'objectKey': key,
                'bucket': bucket,
                'createdTimestamp': timestamp,
                'labels': labels
            }

            print(f"Document to index: {json.dumps(document)}")

            # Step 4: Index document in OpenSearch
            try:
                opensearch_client = get_opensearch_client()

                # Create index if it doesn't exist
                if not opensearch_client.indices.exists(index=OPENSEARCH_INDEX):
                    opensearch_client.indices.create(index=OPENSEARCH_INDEX)
                    print(f"Created index: {OPENSEARCH_INDEX}")

                # Index the document
                response = opensearch_client.index(
                    index=OPENSEARCH_INDEX,
                    body=document,
                    refresh=True
                )

                print(f"Successfully indexed document: {response}")

            except Exception as e:
                print(f"Error indexing to OpenSearch: {str(e)}")
                raise

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Photo indexed successfully',
                'labels': labels
            })
        }

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error indexing photo',
                'error': str(e)
            })
        }

# Test pipeline