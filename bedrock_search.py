import boto3
import json

# Initialize Bedrock client
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Define input parameters
payload = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 200,
    "top_k": 250,
    "stop_sequences": [],
    "temperature": 1,
    "top_p": 0.999,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What is the capital of the Japan? If you know write a poem for me."
                }
            ]
        }
    ]
}

# Convert to JSON format
body = json.dumps(payload)

# Choose inference profile ID
model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

# Invoke model
response = bedrock_client.invoke_model(
    modelId=model_id,
    contentType="application/json",
    accept="application/json",
    body=body
)

# Parse response
response_body = json.loads(response['body'].read())
print(response_body['content'][0]['text'])
