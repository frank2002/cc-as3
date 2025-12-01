import json
import boto3
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import uuid

# Initialize AWS clients
lex_client = boto3.client('lexv2-runtime')

# OpenSearch configuration
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')
OPENSEARCH_REGION = os.environ.get('AWS_REGION', 'us-east-1')
OPENSEARCH_INDEX = 'photos'

# Lex Bot configuration
LEX_BOT_ID = os.environ.get('LEX_BOT_ID', '')
LEX_BOT_ALIAS_ID = os.environ.get('LEX_BOT_ALIAS_ID', '')
LEX_LOCALE_ID = os.environ.get('LEX_LOCALE_ID', 'en_US')

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

def disambiguate_query(query_text):
    """
    Use Amazon Lex to extract keywords from the search query

    Args:
        query_text: Natural language search query

    Returns:
        List of keywords extracted by Lex
    """
    try:
        print(f"Disambiguating query with Lex: {query_text}")

        response = lex_client.recognize_text(
            botId=LEX_BOT_ID,
            botAliasId=LEX_BOT_ALIAS_ID,
            localeId=LEX_LOCALE_ID,
            sessionId=str(uuid.uuid4()),
            text=query_text
        )

        print(f"Lex response: {json.dumps(response, default=str)}")

        keywords = []

        # Extract keywords from slots
        if 'sessionState' in response and 'intent' in response['sessionState']:
            intent = response['sessionState']['intent']

            if 'slots' in intent:
                slots = intent['slots']

                # Extract values from all slots
                for slot_name, slot_value in slots.items():
                    if slot_value and 'value' in slot_value:
                        value = slot_value['value']['interpretedValue']
                        if value:
                            keywords.append(value.lower())

        print(f"Extracted keywords: {keywords}")
        return keywords

    except Exception as e:
        print(f"Error in Lex disambiguation: {str(e)}")
        # Fallback: split query by common words
        fallback_keywords = []
        query_lower = query_text.lower()

        # Remove common words
        stop_words = ['show', 'me', 'photos', 'with', 'of', 'and', 'in', 'the', 'a', 'an']
        words = query_lower.split()

        for word in words:
            cleaned_word = word.strip('.,!?')
            if cleaned_word and cleaned_word not in stop_words:
                fallback_keywords.append(cleaned_word)

        print(f"Using fallback keywords: {fallback_keywords}")
        return fallback_keywords

def search_photos(keywords):
    """
    Search OpenSearch for photos matching the given keywords

    Args:
        keywords: List of keywords to search for

    Returns:
        List of photo objects matching the search
    """
    try:
        if not keywords:
            print("No keywords provided for search")
            return []

        opensearch_client = get_opensearch_client()

        # Build search query - match any of the keywords
        search_body = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"labels": keyword}} for keyword in keywords
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": 100
        }

        print(f"OpenSearch query: {json.dumps(search_body)}")

        response = opensearch_client.search(
            index=OPENSEARCH_INDEX,
            body=search_body
        )

        print(f"OpenSearch response: {json.dumps(response, default=str)}")

        # Extract photos from response
        photos = []
        if 'hits' in response and 'hits' in response['hits']:
            for hit in response['hits']['hits']:
                source = hit['_source']
                photos.append({
                    'url': f"https://{source['bucket']}.s3.amazonaws.com/{source['objectKey']}",
                    'labels': source.get('labels', [])
                })

        print(f"Found {len(photos)} photos")
        return photos

    except Exception as e:
        print(f"Error searching OpenSearch: {str(e)}")
        return []

def lambda_handler(event, context):
    """
    Lambda function to search for photos using natural language queries

    Workflow:
    1. Extract query from request
    2. Use Lex to disambiguate query and extract keywords
    3. Search OpenSearch for matching photos
    4. Return results
    """

    try:
        print(f"Received event: {json.dumps(event)}")

        # Extract query from event
        query_text = ""

        # Check different event formats (API Gateway, direct invoke, etc.)
        if 'queryStringParameters' in event and event['queryStringParameters']:
            query_text = event['queryStringParameters'].get('q', '')
        elif 'q' in event:
            query_text = event['q']
        elif 'query' in event:
            query_text = event['query']

        if not query_text:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({
                    'error': 'Missing query parameter "q"'
                })
            }

        print(f"Search query: {query_text}")

        # Step 1: Disambiguate query using Lex
        keywords = disambiguate_query(query_text)

        # Step 2: Search photos
        photos = search_photos(keywords)

        # Step 3: Return results
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'results': photos,
                'keywords': keywords
            })
        }

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
